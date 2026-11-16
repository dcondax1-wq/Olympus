"""DST audit (2026-10-29): US clocks go back Sun 2026-11-01 02:00 ET (EDT -> EST). Every time decision of the bots must stay
on the ET wall clock on both sides of a switch: fall 2025-11-02, spring 2026-03-08 and the coming fall 2026-11-01.

    python -X utf8 -m tests.test_dst           # all (~1 min: + LIT live-loop replays over the DST weeks, real bars)
    python -X utf8 -m tests.test_dst --quick   # pure functions only (seconds)

 1. tzdata knows the switches (01:59 EDT -> 01:00 EST at 06:00 UTC; 01:59 EST -> 03:00 EDT at 07:00 UTC).
 2. Every trading_day / session_day function (24 of them: PC bot, adapters, ATLAS / account B, extra accounts, narrator,
    board, goals, audits...): Sun 18:00 ET opens Monday's session, 17:59 / 01:59 / 02:00 / 15:55 / 16:59 stay on the date,
    18:00 opens the next one, on both sides of each switch.
 3. market_open (live, ops_checks, go): Sun 18:00 opens, 17:00-18:00 break, Fri 17:00 close, both sides.
 4. Entry / flat windows land on the same ET minutes on both sides: guards.calendar (LIT + ATLAS route), the NinjaTrader
    adapter's entry gate and its 15:55 flat watch, account B's / the second strategies' 15:55 flat, ATLAS paper
    _session_open, lit_live._session_over / window_start, BLITZ's check minutes, live_board.next_windows.
 5. Automation windows: auto-update blackout 01:50-16:00 ET and the 01:20 hourly stop, the 17:02 halt check, ops pushes
    (01:40 pre-session, 16:05 day summary), the cloud's "PC offline" window 01:30-16:00.
 6. The cloud monitor's UTC crons + its ET guard (the real bash step of .github/workflows/cloud-monitor.yml with a fake
    `date`): on every weekday of the DST weeks the night check runs at 01:32 ET, runs every 30 min to 16:32 ET, none
    before 01:30 or after 16:40 ET, with GitHub's start delays (0 / 20 min) too.
 7. No fixed ET offsets in the live code (engine/, cloud monitor, watcher; LE_BarFeed.cs converts with NinjaTrader's
    TimeZoneInfo); the phone / PC JS fallback (no Intl) follows the US rule (node: == Intl on every hour 2021-2030).
 8. (full run) LIT live loop (engine/lit_live.run, what the PC bot and the cloud run every poll) over the DST weeks of fall
    2025 (5m), spring 2025 (5m) and spring 2026 (1m): day-end replay + intraday polls == the backtest trade for trade;
    every backtest trade 2021-2026 enters from 02:00 ET before the flat and exits by the 15:55 flat (or a CME early close).
Temp dirs only; nothing in data/ or the live config is written.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
RESULTS = []
# (the Sunday of the switch, kind)
SWITCHES = [(dt.date(2025, 11, 2), "fall"), (dt.date(2026, 3, 8), "spring"), (dt.date(2026, 11, 1), "fall")]


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(d: dt.date, hh: int, mm: int = 0) -> int:
    return int(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).timestamp())


def sides(sun: dt.date):
    """(label, Monday, Friday) of the week before and the week after the switch Sunday."""
    return [("before", sun - dt.timedelta(days=6), sun - dt.timedelta(days=2)),
            ("after", sun + dt.timedelta(days=1), sun + dt.timedelta(days=5))]


# ------------------------------------------------------------------------------------------------ 1. tzdata
def t_tzdata():
    print("1. tzdata knows the switches", flush=True)
    a = dt.datetime(2026, 11, 1, 5, 59, tzinfo=UTC).astimezone(ET)
    b = dt.datetime(2026, 11, 1, 6, 0, tzinfo=UTC).astimezone(ET)
    c = dt.datetime(2026, 3, 8, 6, 59, tzinfo=UTC).astimezone(ET)
    d = dt.datetime(2026, 3, 8, 7, 0, tzinfo=UTC).astimezone(ET)
    check("2026-11-01: 05:59 UTC = 01:59 EDT, 06:00 UTC = 01:00 EST; 2026-03-08: 06:59 UTC = 01:59 EST, 07:00 UTC = 03:00 EDT",
          (a.strftime("%H:%M %Z"), b.strftime("%H:%M %Z"), c.strftime("%H:%M %Z"), d.strftime("%H:%M %Z"))
          == ("01:59 EDT", "01:00 EST", "01:59 EST", "03:00 EDT"), (a, b, c, d))
    sw, t = [], int(dt.datetime(2021, 1, 1, tzinfo=UTC).timestamp())
    end = int(dt.datetime(2036, 1, 1, tzinfo=UTC).timestamp())
    prev = dt.datetime.fromtimestamp(t, ET).utcoffset()
    while t < end:
        t += 3600
        off = dt.datetime.fromtimestamp(t, ET).utcoffset()
        if off != prev:
            sw.append(dt.datetime.fromtimestamp(t - 1, ET))      # the last second before the switch (ET wall clock)
        prev = off
    check(f"all {len(sw)} US switches 2021-2035 happen on a Sunday at 01:59:59 ET (inside the CME weekend Fri 17:00 -> Sun "
          "18:00 ET): no trading session ever spans a switch", len(sw) == 30 and all(e.weekday() == 6 and e.hour == 1 for e in sw),
          [str(e) for e in sw if not (e.weekday() == 6 and e.hour == 1)])


# ------------------------------------------------------------------------------------------------ 2. trading days
def _td_funcs():
    from engine import (accounts, account_b, ai_watch, alerts_plus, broker_balance, cme_calendar, dash_data, fill_audit, goals,
                        guards, handsoff, insight_api, live, live_board, live_learning, lit_live, memory, multi_account,
                        narrator, ninjatrader, ops_checks, presence, second, atlas_v2)
    plain = {"live": live.trading_day, "accounts": accounts.trading_day, "account_b": account_b.trading_day,
             "atlas_v2": atlas_v2.trading_day, "ai_watch": ai_watch.trading_day, "alerts_plus": alerts_plus._trading_day,
             "broker_balance": broker_balance._trading_day, "dash_data": dash_data.trading_day,
             "fill_audit": fill_audit.trading_day, "goals": goals.trading_day, "guards": guards.trading_day,
             "handsoff": handsoff.trading_day, "live_board": live_board.trading_day, "live_learning": live_learning.trading_day,
             "memory": memory.trading_day, "multi_account": multi_account.trading_day, "narrator": narrator.trading_day,
             "ninjatrader": ninjatrader._trading_day, "ops_checks": ops_checks.trading_day, "presence": presence.trading_day,
             "second": second.trading_day, "lit_live": lambda t: lit_live.trading_date(t).isoformat(),
             "cme_calendar": lambda t: cme_calendar.trading_date(t).isoformat()}
    from engine import go
    weekday = {"insight_api": insight_api.trading_day,
               "go.session_day": lambda t: go.session_day(dt.datetime.fromtimestamp(int(t), ET))}
    return plain, weekday


def t_trading_days():
    print("2. trading-day functions across the switches", flush=True)
    plain, weekday = _td_funcs()
    for sun, kind in SWITCHES:
        mon = sun + dt.timedelta(days=1)
        fri = sun - dt.timedelta(days=2)
        cases = [  # (ET date, hh, mm, plain date, weekday-skipping date)
            (fri, 0, 30, fri, fri), (fri, 16, 59, fri, fri),
            (sun, 17, 59, sun, mon), (sun, 18, 0, mon, mon), (sun, 23, 59, mon, mon),
            (mon, 0, 30, mon, mon), (mon, 1, 59, mon, mon), (mon, 2, 0, mon, mon), (mon, 15, 55, mon, mon),
            (mon, 16, 59, mon, mon), (mon, 18, 0, mon + dt.timedelta(days=1), mon + dt.timedelta(days=1))]
        bad = []
        for d, hh, mm, want, want_wd in cases:
            t = ts(d, hh, mm)
            for name, f in plain.items():
                got = f(t)
                if str(got) != want.isoformat():
                    bad.append((name, f"{d} {hh:02d}:{mm:02d}", got, want.isoformat()))
            for name, f in weekday.items():
                got = f(t)
                if str(got) != want_wd.isoformat():
                    bad.append((name, f"{d} {hh:02d}:{mm:02d}", got, want_wd.isoformat()))
        check(f"{kind} {sun}: {len(plain) + len(weekday)} trading-day functions put Sun 18:00 ET in Monday's session and keep "
              "01:59 / 02:00 / 15:55 / 16:59 ET on the date, Fri before and Mon after", not bad, bad[:8])
    # the night of the switch itself: every minute 2026-10-31 12:00 -> 2026-11-02 12:00 UTC is one trading date per function
    t0 = int(dt.datetime(2026, 10, 31, 12, 0, tzinfo=UTC).timestamp())
    f, g = plain["live"], plain["cme_calendar"]
    bad = [t for t in range(t0, t0 + 48 * 3600, 60) if f(t) != g(t)]
    check("2026-10-31 12:00 -> 11-02 12:00 UTC (the fall-back night, the 01:00-02:00 ET hour twice): live.trading_day == "
          "cme_calendar.trading_date on every minute", not bad, bad[:3])


# ------------------------------------------------------------------------------------------------ 3. market open
def t_market_open():
    print("3. market open / closed across the switches", flush=True)
    from engine import go, live, ops_checks
    fns = {"live": live.market_open, "ops_checks": ops_checks.market_open,
           "go": lambda t: go.market_open(dt.datetime.fromtimestamp(int(t), ET))}
    for sun, kind in SWITCHES:
        mon, fri = sun + dt.timedelta(days=1), sun - dt.timedelta(days=2)
        cases = [(fri, 16, 59, True), (fri, 17, 0, False), (sun, 17, 59, False), (sun, 18, 0, True), (mon, 1, 30, True),
                 (mon, 16, 59, True), (mon, 17, 0, False), (mon, 17, 59, False), (mon, 18, 0, True)]
        bad = [(n, f"{d} {hh:02d}:{mm:02d}", want) for n, f in fns.items() for d, hh, mm, want in cases if bool(f(ts(d, hh, mm))) != want]
        check(f"{kind} {sun}: market_open (live / ops_checks / go) Fri 16:59 open, 17:00 shut, Sun 17:59 shut, 18:00 open, "
              "Mon 17:00-17:59 break", not bad, bad)


# ------------------------------------------------------------------------------------------------ 4. entry / flat windows
def _adapter(tmp, now):
    from engine.ninjatrader import NinjaTraderAdapter
    folder = os.path.join(tmp, "NT")
    os.makedirs(os.path.join(folder, "incoming"), exist_ok=True)
    os.makedirs(os.path.join(folder, "outgoing"), exist_ok=True)
    cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": folder, "params": {"max_micros": 40, "flat_mod": 955},
           "model": "lit", "model_params": {"window": [[120, 930]]}, "nt_state_path": os.path.join(tmp, "nt_state.json"),
           "nt_audit_log": os.path.join(tmp, "oif.log")}
    return NinjaTraderAdapter(cfg, clock=lambda: now[0])


def t_windows(tmp):
    print("4. entry / flat windows on the same ET minutes on both sides", flush=True)
    from engine import account_b, blitz, guards, lit_live, live, live_board, second
    now = [0.0]
    ad = _adapter(tmp, now)
    closed = []
    ad._close = lambda legs, why="": closed.append(why)
    ad._our_instruments = lambda: []
    for sun, kind in SWITCHES:
        for side, mon, fri in sides(sun):
            for d in (mon, fri):
                lab = f"{kind} {sun} {side} {d:%a %m-%d}"
                # guards.calendar (LIT's and ATLAS's route guard)
                g = {hm: guards.calendar(ts(d, *hm), ts(d, *hm), session_from=120, flat_mod=955)
                     for hm in ((1, 59), (2, 0), (15, 54), (15, 55), (17, 30))}
                ok_g = bool(g[(1, 59)]) and not g[(2, 0)] and not g[(15, 54)] and bool(g[(15, 55)]) and "market closed" in g[(17, 30)][0]
                # the NinjaTrader adapter's own entry gate
                gate = {}
                for hm in ((1, 59), (2, 0), (15, 54), (15, 55)):
                    now[0] = ts(d, *hm)
                    gate[hm] = ad._gate("entry")
                ok_a = gate[(1, 59)] and gate[(2, 0)] is None and gate[(15, 54)] is None and gate[(15, 55)]
                # the adapter's flat watch: a leg open at 15:54 stays, at 15:55 it is flattened
                closed.clear()
                ad.legs = [{"status": "protected", "instrument": "MNQ 12-26", "entry_id": "x"}]
                ad._tick_flat_time(ts(d, 15, 54))
                quiet = not closed
                ad._tick_flat_time(ts(d, 15, 55))
                ok_f = quiet and closed == ["flat time"]
                ad.legs = []
                # account B / second strategies on the LIT account / ATLAS paper: 15:55 ET of the trade's day
                pv = {"day": d.isoformat()}
                ok_b = (not account_b.AccountB._past_flat(None, pv, ts(d, 15, 54)) and account_b.AccountB._past_flat(None, pv, ts(d, 15, 55))
                        and not live.LiveBot._second_past_flat(None, pv, ts(d, 15, 54)) and live.LiveBot._second_past_flat(None, pv, ts(d, 15, 55)))
                ok_s = second._session_open(d.isoformat(), ts(d, 15, 54), ts(d, 15, 50)) and not second._session_open(d.isoformat(), ts(d, 15, 55), ts(d, 15, 50))
                ok_l = (not lit_live._session_over(d.isoformat(), ts(d, 16, 59)) and lit_live._session_over(d.isoformat(), ts(d, 17, 0))
                        and dt.datetime.fromtimestamp(lit_live.window_start(ts(d, 12)), ET).strftime("%H:%M") == "18:00")
                # BLITZ: the 11:00 ET check minute and the 15:55 flat bar sit on the ET clock
                ok_z = (blitz.et_parts(blitz.at_et(d.isoformat(), 659)) == (d.isoformat(), 659)
                        and dt.datetime.fromtimestamp(blitz.at_et(d.isoformat(), blitz.LAST_IN), ET).strftime("%H:%M") == "15:54")
                # the board's next entry windows (absolute times): 02:00-15:30 ET
                w = live_board.next_windows(ts(d, 0, 30), [[120, 930]], n=1)
                ok_w = bool(w) and [dt.datetime.fromtimestamp(w[0][k], ET).strftime("%H:%M") for k in ("open_t", "close_t")] == ["02:00", "15:30"]
                check(f"{lab}: calendar guard / adapter gate refuse 01:59 + 15:55, allow 02:00 + 15:54; adapter flattens at 15:55 "
                      "not 15:54; account B / second flat 15:55; ATLAS paper open to 15:54; LIT session over 17:00, window from 18:00; "
                      "BLITZ 11:00 check + 15:54 flat bar; board window 02:00-15:30",
                      all((ok_g, ok_a, ok_f, ok_b, ok_s, ok_l, ok_z, ok_w)),
                      {"guard": ok_g, "adapter": ok_a, "flat": ok_f, "B": ok_b, "second": ok_s, "lit": ok_l, "blitz": ok_z, "board": ok_w,
                       "g": g, "gate": gate, "w": w})
    # BLITZ caches ET per UTC hour: every minute of both switch nights == zoneinfo
    from engine import blitz as Z
    bad = []
    for start in (dt.datetime(2026, 10, 31, 20, 0, tzinfo=UTC), dt.datetime(2026, 3, 7, 20, 0, tzinfo=UTC), dt.datetime(2025, 11, 1, 20, 0, tzinfo=UTC)):
        t0 = int(start.timestamp())
        for t in range(t0, t0 + 36 * 3600, 60):
            e = dt.datetime.fromtimestamp(t, ET)
            if Z.et_parts(t) != (e.strftime("%Y-%m-%d"), e.hour * 60 + e.minute):
                bad.append(t)
    check("BLITZ et_parts (cached per UTC hour) == zoneinfo on every minute of the 2025-11-02, 2026-03-08 and 2026-11-01 nights",
          not bad, bad[:3])


# ------------------------------------------------------------------------------------------------ 5. automation windows
def t_automation():
    print("5. auto-update / ops pushes / PC-offline windows", flush=True)
    from engine import autoupdate as AU, ops_checks as OC, push
    for sun, kind in SWITCHES:
        for side, mon, fri in sides(sun):
            d = mon
            bl = [AU.in_blackout(ts(d, *hm)) for hm in ((1, 49), (1, 50), (15, 59), (16, 0))]
            hr = [AU.window_reason(ts(d, *hm), "hourly") for hm in ((1, 19), (1, 20), (16, 0))]
            dy = [AU.window_reason(ts(d, *hm), "daily") for hm in ((17, 1), (17, 2), (17, 50), (17, 51))]
            du = OC.due(ts(d, 1, 40)), OC.due(ts(d, 1, 39)), OC.due(ts(d, 16, 5)), OC.due(ts(d, 16, 4))
            po = [push.pc_offline_window(ts(d, *hm)) for hm in ((1, 29), (1, 30), (16, 0), (16, 1))]
            ok = (bl == [False, True, True, False] and hr[0] is None and hr[1] and hr[2] is None
                  and [x is None for x in dy] == [False, True, True, False]
                  and du[0]["presession"] and not du[1]["presession"] and du[2]["eod"] and not du[3]["eod"]
                  and po == [False, True, True, False])
            check(f"{kind} {sun} {side} {d:%a %m-%d}: update blackout 01:50-16:00, hourly stop 01:20, halt check 17:02-17:50, "
                  "pre-session push 01:40, day summary 16:05, PC-offline window 01:30-16:00 ET", ok,
                  {"blackout": bl, "hourly": hr, "daily": dy, "due": [x.get("presession") or x.get("eod") for x in du], "pc": po})
    # hour_key on the fall-back night: the repeated 01:00 ET hour is one key (an hourly check runs once, never twice)
    k = {AU.hour_key(int(dt.datetime(2026, 11, 1, h, 30, tzinfo=UTC).timestamp())) for h in (5, 6)}
    check("auto-update hour_key: 01:30 EDT and 01:30 EST (Sun 2026-11-01, the weekend) are the same hour: at most one hourly check",
          k == {"2026-11-01T01"}, k)


# ------------------------------------------------------------------------------------------------ 6. cloud crons + guard
def _guard_script():
    import yaml
    wf = yaml.safe_load(open(os.path.join(ROOT, ".github", "workflows", "cloud-monitor.yml"), encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    crons = [c["cron"] for c in on["schedule"]]
    step = next(s for s in wf["jobs"]["monitor"]["steps"] if s.get("id") == "guard")
    return crons, step["run"]


def _cron_times(expr: str, start: dt.datetime, end: dt.datetime) -> list:
    """UTC firing times of a 5-field cron with lists / ranges in minute and hour, '*' for day / month, a list / range of
    weekdays (0 = Sunday)."""
    def field(f, lo, hi):
        if f == "*":
            return set(range(lo, hi + 1))
        out = set()
        for part in f.split(","):
            if "-" in part:
                a, b = part.split("-")
                out |= set(range(int(a), int(b) + 1))
            else:
                out.add(int(part))
        return out
    mi, hh, dom, mon, dow = expr.split()
    M, H, W = field(mi, 0, 59), field(hh, 0, 23), field(dow, 0, 6)
    out, t = [], start
    while t < end:
        if t.minute in M and t.hour in H and ((t.weekday() + 1) % 7) in W:
            out.append(t)
        t += dt.timedelta(minutes=1)
    return out


def t_cloud(tmp):
    print("6. cloud monitor: UTC crons + the ET guard step (real bash, fake date)", flush=True)
    bash, real_date = shutil.which("bash"), shutil.which("date")
    if not bash or not real_date or os.name == "nt":
        check("cloud guard: bash + GNU date not available here (Windows): skipped", True)
        return
    crons, script = _guard_script()
    shim = os.path.join(tmp, "shim")
    os.makedirs(shim, exist_ok=True)
    with open(os.path.join(shim, "date"), "w") as fh:
        fh.write(f'#!/bin/sh\nexec "{real_date}" -d "@$FAKE_EPOCH" "$@"\n')
    with open(os.path.join(shim, "curl"), "w") as fh:       # the Actions budget read (tests/test_selfheal.py): no file here
        fh.write("#!/bin/sh\nexit 22\n")
    for f in ("date", "curl"):
        os.chmod(os.path.join(shim, f), 0o755)

    def run_guard(t: dt.datetime, cron: str) -> bool:
        s = script.replace("${{ github.event_name }}", "schedule").replace("${{ github.event.schedule }}", cron) \
            .replace("${{ github.repository }}", "owner/repo").replace("${{ github.token }}", "x")
        out = os.path.join(tmp, "gh_out")
        open(out, "w").close()
        env = {**os.environ, "PATH": shim + os.pathsep + os.environ.get("PATH", ""), "FAKE_EPOCH": str(int(t.timestamp())),
               "GITHUB_OUTPUT": out}
        subprocess.run([bash, "-e", "-c", s], env=env, capture_output=True, text=True, timeout=20)
        return "go=1" in open(out).read()

    for sun, kind in SWITCHES:
        start = dt.datetime.combine(sun - dt.timedelta(days=7), dt.time(0, 0), UTC)
        end = dt.datetime.combine(sun + dt.timedelta(days=7), dt.time(0, 0), UTC)
        for delay in (0, 20):
            runs = {}
            sunday = []
            for c in crons:
                for t in _cron_times(c, start, end):
                    t2 = t + dt.timedelta(minutes=delay)
                    if run_guard(t2, c):
                        e = t2.astimezone(ET)
                        if c.endswith("* * 0"):
                            sunday.append(e)
                        else:
                            runs.setdefault(e.date(), []).append(e.hour * 60 + e.minute)
            bad = []
            for d, mods in sorted(runs.items()):
                mods.sort()
                night = [m for m in mods if m < 120]
                day_ = [m for m in mods if 120 <= m]
                if d.weekday() >= 5 or not night or min(mods) < 90 or max(mods) > 1000 or len(mods) < 26 \
                        or min(day_) > 125 + delay or max(day_) < 960:
                    bad.append((d.isoformat(), [f"{m // 60:02d}:{m % 60:02d}" for m in mods[:3]], len(mods),
                                f"{max(mods) // 60:02d}:{max(mods) % 60:02d}"))
            wk = sorted(d for d in runs)
            want = [d for d in (start.date() + dt.timedelta(days=i) for i in range(14)) if d.weekday() < 5]
            check(f"{kind} {sun} (+{delay} min GitHub delay): every weekday of both weeks runs a night check before 02:00 ET, "
                  "the first session run by 02:05 ET, the last at/after 16:00 ET, none before 01:30 or after 16:40 ET",
                  not bad and wk == want, {"bad": bad, "days": [d.isoformat() for d in wk]})
            check(f"{kind} {sun} (+{delay} min): the Sunday learning review fires on Sunday afternoon ET both weeks "
                  "(17:47 EDT / 16:47 EST)", len(sunday) == 2 and all(e.weekday() == 6 and 16 <= e.hour <= 18 for e in sunday),
                  [str(e) for e in sunday])


# ------------------------------------------------------------------------------------------------ 7. static scan + JS
FIXED = re.compile(r"timedelta\(hours=-?[45]\)|['\"][-+]0[45]:00['\"]|UTC-?[45]\b|tz_offset|timezone\(dt\.timedelta\(hours=-[45]")
ALLOW = {  # research-engine 4h buckets (the old engine, a shadow ledger; fixed 22:00 UTC by design, same in the backtest)
    os.path.join("engine", "data.py"), os.path.join("engine", "mtf.py")}


def t_static():
    print("7. no fixed ET offsets in the live code; LE_BarFeed + JS fallbacks", flush=True)
    files = [os.path.join("engine", f) for f in sorted(os.listdir(os.path.join(ROOT, "engine"))) if f.endswith(".py")]
    files += [os.path.join("tools", "cloud_monitor.py"), os.path.join("tools", "lit_watch.py"), "server.py",
              os.path.join("tools", "build_web_dashboard.py"), os.path.join("scripts", "ops_tick.py")]
    hits = []
    for f in files:
        if f in ALLOW:
            continue
        for i, ln in enumerate(open(os.path.join(ROOT, f), encoding="utf-8", errors="replace"), 1):
            code = ln.split("#", 1)[0]
            if FIXED.search(code):
                hits.append(f"{f}:{i}: {ln.strip()[:100]}")
    check(f"{len(files)} live-code files: no fixed ET offset (timedelta(hours=-4/-5), '-04:00', UTC-4, ...)", not hits, hits[:6])
    cs = open(os.path.join(ROOT, "ninjatrader", "LE_BarFeed.cs"), encoding="utf-8").read()
    check("LE_BarFeed.cs: bar stamps converted with NinjaTrader's TimeZoneInfo to UTC (no fixed hour offset)",
          cs.count("TimeZoneInfo.ConvertTimeToUtc") >= 2 and not re.search(r"AddHours\(\s*-?[45]\s*\)", cs))
    node = shutil.which("node")
    srcs = [os.path.join(ROOT, p) for p in ("web_next/js/litkit.js", "tools/web_public/litkit.js",
                                            "web_next/js/tradechart.js", "tools/web_public/tradechart.js")]
    texts = [open(p, encoding="utf-8").read() for p in srcs]
    fixed_js = [p for p, s in zip(srcs, texts) if re.search(r"getTime\(\)\s*-\s*4\s*\*\s*3600|catch\s*\{\s*return\s*-4\s*\*\s*3600", s)]
    # the phone and PC copies differ on purpose elsewhere (PC: AGORA palette 2026-11-10; phone: real-eval card, -webkit- twins), so
    # what must match is the ET time code itself: litkit.js ETF .. etEpoch, tradechart.js usEtOff .. etOffset
    def tz_block(s, start, last):
        i = s.find(start)
        j = s.find("\n}", s.find("function " + last + "(", i))
        return s[i:j] if i >= 0 and j > i else None
    lk = [tz_block(t, "const ETF", "etEpoch") for t in texts[:2]]
    tc = [tz_block(t, "function usEtOff", "etOffset") for t in texts[2:]]
    check("phone / PC JS: no fixed -4 h fallback left (litkit.js, tradechart.js; phone and PC copies' ET time code identical)",
          not fixed_js and lk[0] and lk[0] == lk[1] and tc[0] and tc[0] == tc[1], fixed_js or ["ET time code differs between web_next/js and tools/web_public"])
    if not node:
        check("node not installed: the JS US-rule check skipped", True)
        return
    fn = next(ln for ln in texts[0].splitlines() if ln.startswith("function usEtOff"))
    js = fn + """
const f = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', timeZoneName: 'shortOffset' });
let bad = [], n = 0;
for (let t = Date.UTC(2021, 0, 1) / 1000; t < Date.UTC(2031, 0, 1) / 1000; t += 3600) {
  const name = f.formatToParts(new Date(t * 1000)).find(p => p.type === 'timeZoneName').value;   // GMT-4 / GMT-5
  const want = name === 'GMT-4' ? -4 * 3600 : -5 * 3600; n++;
  if (usEtOff(t) !== want) bad.push(new Date(t * 1000).toISOString());
}
console.log(JSON.stringify({ n, bad: bad.slice(0, 5), nbad: bad.length }));
"""
    p = os.path.join(tempfile.gettempdir(), f"usetoff_{os.getpid()}.js")
    open(p, "w", encoding="utf-8").write(js)
    try:
        r = json.loads(subprocess.run([node, p], capture_output=True, text=True, timeout=60).stdout)
    finally:
        os.remove(p)
    check(f"JS usEtOff (the no-Intl fallback) == Intl America/New_York on all {r['n']:,} hours 2021-2030", r["nbad"] == 0, r)


# ------------------------------------------------------------------------------------------------ 8. LIT live-loop replay
def t_replay():
    print("8. LIT live loop over the DST weeks (real bars) == the backtest", flush=True)
    import numpy as np
    import pandas as pd
    from engine import lit_live
    from engine.data import load, load_ltf
    from tests.test_lit_live import day_close, key, ref_exit, ref_key
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    REF = F.run(P)
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    T5 = df5["time"].values
    b1, _ = load_ltf("NQ", load("NQ", "5m"))

    def poll(now, early=True):
        cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
        cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        jf = int(np.searchsorted(b1.t, now - now % 60))
        forming = (int(b1.t[jf]), float(b1.o[jf])) if jf < len(b1.t) and int(b1.t[jf]) == now - now % 60 else None
        return lit_live.run(cut5, P, one_min=cut1 if len(cut1) else None, now=now, forming=forming, early=early)

    for lo, hi, label in (("2025-10-20", "2025-11-14", "fall 2025-11-02 (5m bars)"),
                          ("2025-03-03", "2025-03-21", "spring 2025-03-09 (5m bars)"),
                          ("2026-02-23", "2026-03-20", "spring 2026-03-08 (1m bars)")):
        sess = [d for d in F.SESS if lo <= d <= hi]
        want = {}
        for t in REF:
            if lo <= t["day"] <= hi:
                want.setdefault(t["day"], []).append(t)
        same, bad = 0, []
        for d in sess:
            res = poll(day_close(d))
            got = {key(t): t for t in res["trades"] if t["day"] == d}
            for w in want.get(d, []):
                g = got.pop(ref_key(w), None)
                if g is not None and (g["exit_reason"], g["exit_t"], round(g["pnl"], 2)) == ref_exit(w):
                    same += 1
                else:
                    bad.append((d, "day-end differs"))
            bad += [(d, "extra", k) for k in got]
        # intraday polls on the trade days: every 5m close from 01:55 ET to 10 min after the exit + every minute near the entry
        polls = 0
        for d, ws in sorted(want.items()):
            w = ws[0]
            ent, ext = int(w["entry_t"]), int(w["exit_t"])
            d0 = dt.date.fromisoformat(d)
            times = set(range(ts(d0, 1, 55), min(ext + 600, day_close(d)) + 1, 300)) | set(range(ent - 300, ent + 301, 60))
            for now in sorted(times):
                polls += 1
                res = poll(now)
                pos = res["state"].get("position")
                if pos:
                    pk = (pos["entry_t"], pos["dir"], round(pos["entry"], 2), round(pos["stop0"], 2), round(pos["target"], 2), pos["qty"])
                    if pk != ref_key(w):
                        bad.append((d, now, "open position differs"))
                for t in res["trades"]:
                    if t["day"] == d and key(t) != ref_key(w):
                        bad.append((d, now, "finished trade differs"))
        n = sum(len(v) for v in want.values())
        check(f"{label}: {len(sess)} sessions, {n} backtest trades: day-end {same}/{n} identical, {polls} intraday polls, "
              f"0 differences", n > 0 and same == n and not bad, bad[:5])
    # every backtest trade 2021-2026: entry inside the ET window, exit by the flat / early close, on both sides of every switch
    from engine import cme_calendar
    badw = []
    for t in REF:
        e = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
        x = dt.datetime.fromtimestamp(int(t["exit_t"]), ET)
        m, xm = e.hour * 60 + e.minute, x.hour * 60 + x.minute
        ec = cme_calendar.early_close(t["day"])
        # (the backtest has no 15-min cut before an early close: 2025-07-03 entered 13:05 before the 13:15 halt; the live
        # calendar guard refuses that one; this check is about the clock, not that rule)
        if not (120 <= m < (ec if ec is not None else 955)) or xm > (ec if ec is not None else 960) or e.date().isoformat() != t["day"]:
            badw.append((t["day"], f"{e:%H:%M}", f"{x:%H:%M}"))
    check(f"all {len(REF)} backtest trades 2021-11 -> 2026-10 (10 DST switches): entry from 02:00 ET before the flat / halt (a 15:30 setup's limit may fill to 15:54), "
          "exit by the 15:55 flat (exit stamp <= 16:00, the 15:55 bar's close on 5m) or the early close", not badw and len(REF) > 500, badw[:5])


def main():
    quick = "--quick" in sys.argv
    tmp = tempfile.mkdtemp(prefix="le_dst_")
    try:
        t_tzdata()
        t_trading_days()
        t_market_open()
        t_windows(tmp)
        t_automation()
        t_cloud(tmp)
        t_static()
        if not quick:
            t_replay()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nDST: {n_ok}/{len(RESULTS)} checks passed")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
