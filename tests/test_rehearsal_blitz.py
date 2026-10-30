"""BLITZ dress rehearsal: account C (BLITZ, the scalper, on its own 25K) through the REAL server.py + a fake NinjaTrader 8 +
a virtual clock, next to LIT (Zlarior, Sim101) and ATLAS (account B, Sim102). BLITZ trades Sim103. Built on the LIT
rehearsal's machinery (tests/test_rehearsal.py: sandbox copy of the repo, LE_BarFeed files fed bar by bar from
data/NQ_1m.csv + data/NQ_5m.csv, a responder thread playing NinjaTrader's ATI, the owner's clicks over HTTP).

    python -X utf8 -m tests.test_rehearsal_blitz --jobs=4          # every day below, ~20 min on 4 busy cores
    python -X utf8 -m tests.test_rehearsal_blitz --days=2026-06-05 [--keep]      # one day (a date or a kind: --days=restart)
    python -X utf8 -m tests.test_rehearsal_blitz --summary=<parts folder>         # rebuild the result file from the day parts

2026-10-29: 345/345 checks on the 10 days; 27 routed BLITZ trades = the backtest, 0 opposite fills (blitz_rehearsal.json).

Sim / paper only: no real account is armed, the live phrase is never written, NINJATRADER_LIVE is never set.

Every routed BLITZ trade is compared with engine.blitz's backtest of the same day (engine.blitz.execute on the 2026 1m
bars), except where the no-hedging rule (LIT > ATLAS > BLITZ) changes it: a BLITZ candidate opposite to LIT / ATLAS is
masked at the signal (no trade, the slot stays free: the expected trades are the backtest with those signals removed, and
each mask must name LIT / ATLAS holding / entering / armed the other way), and an opposite LIT / ATLAS entry while BLITZ
is open closes BLITZ at market first (HEDGE). Per trade: entry minute, side, micros (account C's 25K eval size: 40% of the
room for sessions 1-4, <= $600, <= 0.9 x the $600 daily loss left, 20 micros), the MARKET fill (= the backtest's fill),
the stop + OCO 20R target at NinjaTrader, every trail CHANGE (only ever tighter, = the model's trailed stop), the exit
(reason, minute) and the booked $ (= micros x the backtest's $ a micro). At every NinjaTrader fill that opens or adds to a
position, no other account may hold the other side (MFFU: never long + short across your own accounts).

Days (DAYS below): a normal multi-trade day, ATLAS entering opposite mid-trade, LIT holding / arming the other side,
CME early closes (13:00 / 13:15 halts injected on normal BLITZ days: 2026's real half days had no BLITZ trade), a
server restart mid-trade, an entry NinjaTrader refuses, the owner's pause and HOLD TO KILL. Writes
research/scalp/blitz_rehearsal.json.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests import test_rehearsal as TR  # noqa: E402

ET = TR.ET
TICK = 0.25
LIMIT_S = 10.0
OUT = os.path.join(ROOT, "research", "scalp", "blitz_rehearsal.json")
LIT_ACCT, B_ACCT, C_ACCT = "Sim101", "Sim102", "Sim103"
_real_time, _real_sleep = TR._real_time, TR._real_sleep
EXIT_MAP = {"time": "TIME", "flat": "TIME", "stop": "STOP", "target": "TARGET"}

# day, kind, start / end (ET hh:mm; the owner starts the bot late, so the live loop rebuilds the morning from the bars as
# after any late START), what it exercises
DAYS = [
    ("2026-08-03", "normal", "10:50", "16:05", "6 BLITZ trades (2-8 micros): 30-bar time exits, trail CHANGEs, a trailed stop-out, the 15:55 flat"),
    ("2026-06-05", "pass", "10:50", "14:10", "3 big BLITZ wins pass the 25K on day 1 (+$1,525): EVAL PASSED, no new trade after"),
    ("2026-08-06", "atlas_opp", "10:15", "12:10", "ATLAS (S/R NY reclaim) enters SHORT 11:15 while BLITZ is LONG: BLITZ closed first"),
    ("2026-05-14", "atlas_same", "10:15", "12:40", "BLITZ LONG and ATLAS SHORT decided at the same 11:00 close: ATLAS first, BLITZ closed"),
    ("2026-04-01", "lit_mask", "10:50", "16:05", "LIT holds / arms SHORT in the afternoon: BLITZ's LONG candidates masked (no hedging)"),
    ("2026-10-15", "early_1300", "10:50", "13:20", "CME early close 13:00 (injected): BLITZ's 12:30 trade flat at 12:55, no bars after"),
    ("2026-06-09", "early_1315", "10:50", "13:35", "CME early close 13:15 (injected): the 13:00 signal is not entered (last 15 min)"),
    ("2026-10-16", "restart", "10:50", "13:40", "server RESTART 6 min into BLITZ's 11:00 trade: no duplicate entry, managed after"),
    ("2026-08-28", "refused", "10:50", "13:10", "NinjaTrader REFUSES BLITZ's first entry: never booked, nothing left working"),
    ("2026-05-18", "pause_kill", "10:50", "13:30", "owner pause blocks one BLITZ entry, then HOLD TO KILL mid trade"),
]
EARLY = {"early_1300": 780, "early_1315": 795}
RESTART_AFTER_MIN, KILL_AFTER_MIN = 6, 5

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": "" if ok else str(detail)[:600]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {str(detail)[:600]}" if detail and not ok else ""), flush=True)
    return bool(ok)


et_at, hm = TR.et_at, TR.hm


def at_hm(day, s):
    h, m = s.split(":")
    return et_at(day, int(h), int(m))


# ================================================================================================ --serve (inside the sandbox)
def serve(sandbox, clock_path, port):
    """tests/test_rehearsal.serve plus: the clock file's "position open" slot covers LIT, account B and account C (the
    rehearsal steps the :32 poll while any of them holds a trade), and LE_RH_EARLY="yyyy-mm-dd=minute" makes that date a CME
    early close at that ET minute (engine/cme_calendar.early_close, installed before any engine import)."""
    vc = TR.VClock(clock_path)
    time.time = vc.now
    os.chdir(sandbox)
    sys.path.insert(0, sandbox)
    early = os.environ.get("LE_RH_EARLY", "")
    if early:
        from engine import cme_calendar as CC
        d0, m0 = early.split("=")
        orig = CC.early_close

        def _early(day, _o=orig):
            return int(m0) if str(day)[:10] == d0 else _o(day)
        CC.early_close = _early
    from engine import live
    orig_sleep, orig_poll = live.LiveBot._sleep_s, live.LiveBot.poll_once

    def _sleep_s(self):
        vc.put(7, -1)
        s = orig_sleep(self)
        tgt = time.time() + s
        vc.put(7, tgt)
        while time.time() < tgt - 1e-6 and not self.stop_flag.is_set():
            _real_sleep(0.003)
        return 0.0

    def _open(self):
        # the :32 poll matters for LIT's mid-minute exits; BLITZ and ATLAS decide on bar closes (the :02 poll)
        return 1 if (self.state or {}).get("position") else 0

    def poll_once(self):
        t = time.time()
        vc.put(7, 0)
        vc.put(6, 1)
        try:
            return orig_poll(self)
        finally:
            try:
                vc.put(5, _open(self))
            except Exception:
                vc.put(5, 1)
            vc.put(3, t)
            vc.put(4, vc.get(4) + 1)
            vc.put(6, 0)
    live.LiveBot._sleep_s = _sleep_s
    live.LiveBot.poll_once = poll_once
    from engine import bg_worker
    bg_worker.JOB_TIMEOUT_S = 1e9          # its hung-child timer runs on time.time(): the virtual clock sprints past 600 s
    from engine import dash_data
    dash_data.JOBS_MGR.submit = lambda spec, force=False: False   # the dashboards' 5-year backtests: not part of trading
    import server
    import uvicorn
    server.HEARTBEAT.every_s = 5.0
    uvicorn.run(server.app, host="127.0.0.1", port=int(port), log_level="warning")


class Server(TR.Server):
    def __init__(self, *a, early=None, **kw):
        super().__init__(*a, **kw)
        self.early = early

    def env(self):
        e = super().env()
        if self.early:
            e["LE_RH_EARLY"] = self.early
        return e

    def start(self):
        self.n += 1
        logf = open(os.path.join(self.base, f"server_{self.n}.log"), "w", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "-X", "utf8", os.path.join(self.repo, "tests", "test_rehearsal_blitz.py"), "--serve",
                                      self.repo, self.clock_path, str(self.port)], cwd=self.repo, env=self.env(),
                                     stdout=logf, stderr=subprocess.STDOUT)
        t_end = _real_time() + 240
        while _real_time() < t_end:
            try:
                self.get("/api/health/ping", timeout=2)
                return True
            except Exception:
                if self.proc.poll() is not None:
                    break
                _real_sleep(0.3)
        raise RuntimeError(f"server did not start (see {logf.name})")


class HaltFeed(TR.Feed):
    """LE_BarFeed on a CME early close: the last closed bar is the one ending at the halt, no forming bar after it (the
    files stop changing, as NinjaTrader's do while the market is halted)."""
    halt_t = None

    def publish(self, now):
        if self.halt_t is None or now < self.halt_t:
            return super().publish(now)
        p = os.path.join(self.dir, "MNQ_1m_open.csv")
        saved = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        mt = os.path.getmtime(p) if os.path.exists(p) else None
        super().publish(self.halt_t)
        if saved is not None:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(saved)
            os.utime(p, (mt, mt))


# ================================================================================================ fake NinjaTrader extras
def instrument_nt(nt):
    """The fake NinjaTrader with: a record of every fill that opens / adds to a position while another account holds the
    other side (must stay empty), and a one-shot refusal of account C's next MARKET entry (refused-order day)."""
    nt.hedge_viol = []
    nt.refuse_c = 0
    nt.refused = []
    orig_fill, orig_do = nt._fill, nt._do

    def _fill(oid, qty, px):
        o = nt.orders.get(oid) or {}
        key = (o.get("account"), o.get("instrument"))
        q0 = nt.pos.get(key, [0, 0.0])[0]
        dq = qty if o.get("action") == "BUY" else -qty
        opens = q0 == 0 or (q0 > 0) == (dq > 0)
        if opens:
            for (acct, inst), (q, _) in list(nt.pos.items()):
                if acct != o.get("account") and q and (q > 0) != (dq > 0):
                    nt.hedge_viol.append({"t": nt.vt(), "acct": o.get("account"), "action": o.get("action"), "qty": qty,
                                          "other": acct, "other_q": q})
        return orig_fill(oid, qty, px)

    def _do(line):
        f = line.split(";")
        if nt.refuse_c > 0 and f[0] == "PLACE" and len(f) > 5 and f[1] == C_ACCT and f[5] == "MARKET":
            nt.refuse_c -= 1
            nt.refused.append((nt.vt(), line))
            nt.reject.add("MARKET")
            try:
                return orig_do(line)
            finally:
                nt.reject.discard("MARKET")
        return orig_do(line)
    nt._fill, nt._do = _fill, _do
    return nt


# ================================================================================================ the expected trades
class Expect:
    """engine.blitz on the 2026 1m bars (data/NQ_1m.csv): the frame, its features and its signal list, so a day's trades can
    be rebuilt with any set of masked signals (the no-hedging skips)."""

    def __init__(self):
        import pandas as pd
        from engine import blitz as BZ
        self.BZ = BZ
        df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        self.B = BZ.frame(df)
        self.F = BZ.features(self.B)
        self.S = BZ.signals(self.B, self.F)
        self.plain = {}
        for t in BZ.execute(self.B, self.S):
            self.plain.setdefault(t["day"], []).append(t)

    def day(self, day, masked=()):
        m = {int(x) for x in masked}
        sig = [s for s in self.S if int(self.B["t"][s[0]]) not in m]
        if not m:
            return list(self.plain.get(day, []))
        return [t for t in self.BZ.execute(self.B, sig) if t["day"] == day]

    def trail_stops(self, t):
        """The model's stop after every bar of trade t before its exit bar (manage() replayed): the stops account C must
        route as CHANGEs (tick-rounded, only the tighter ones)."""
        import numpy as np
        BZ, B = self.BZ, self.B
        j = int(np.searchsorted(B["t"], int(t["entry_t"])))
        D = int(t["dir"])
        p = {"dir": D, "fill": float(t["entry"]), "stp": float(t["stop"]), "tg": float(t["entry"]) + D * BZ.TGT_R * float(t["risk_pts"]),
             "risk": float(t["risk_pts"]), "ext": float(t["entry"]), "mae": 0.0, "nb": 0}
        fe = int(B["flat"][j])
        out = []
        for i in range(j, fe + 1):
            p["nb"] = i - j
            x = BZ.manage(p, float(B["o"][i]), float(B["h"][i]), float(B["l"][i]), float(B["c"][i]), i == j, i >= fe)
            if x is not None:
                break
            out.append((int(B["t"][i]) + 60, float(p["stp"])))
        return out


def expected_qty(risk_pts, cum, session=1):
    """Account C's eval size for a fresh Builder 25K (room $1,000 + today's closed $; the floor does not move intraday),
    engine/account_c SIZE_EVAL written out: 40% of the room for sessions 1-4, <= $600, <= 0.9 x the $600 daily loss left,
    20 micros; 1 micro while it fits half the room."""
    room = 1000.0 + cum
    f = 1.0 if session >= 5 else 0.4
    risk_pm = (float(risk_pts) + TICK) * 2.0 + 1.90
    dll_left = 600.0 + cum
    budget = min(600.0, f * room, 0.9 * dll_left)
    if budget <= 0 or room <= 0:
        return 0
    q = int(min(20, budget // risk_pm))
    if q == 0 and risk_pm <= min(0.5 * room, 0.9 * dll_left):
        q = 1
    return q


# ================================================================================================ the rehearsal
class Rehearsal:
    def __init__(self, days, keep=False):
        from engine.ninjatrader import nt_instrument
        self.nt_instrument = nt_instrument
        self.days, self.keep = days, keep
        self.base = tempfile.mkdtemp(prefix="le_rh_blitz_")
        print(f"sandbox {self.base}", flush=True)
        self.repo = TR.build_sandbox(self.base)
        self.nt_folder = os.path.join(self.base, "NinjaTrader 8")
        self.clock_path = os.path.join(self.base, "clock.bin")
        self.vc = TR.VClock(self.clock_path, create=True)
        self.hist = TR.History(self.repo)
        print("loading bars + the BLITZ backtest ...", flush=True)
        self.b1, self.b5 = TR.bars_of("1m"), TR.bars_of("5m")
        self.X = Expect()
        self.nt = instrument_nt(TR.make_nt(self.nt_folder, self.vc))
        self.feed = HaltFeed(self.nt_folder, self.b1, self.b5)
        self.resp = TR.Responder(self.nt)
        self.server = Server(self.base, self.repo, self.clock_path, self.nt_folder)
        self.rows, self.bugs = [], []
        import pandas as pd
        d = pd.to_datetime(self.b5["time"], unit="s", utc=True).dt.tz_convert(ET)
        rth = d[(d.dt.hour * 60 + d.dt.minute >= 570) & (d.dt.hour * 60 + d.dt.minute < 960) & (d.dt.weekday < 5)]
        self.sessions = sorted(set(rth.dt.strftime("%Y-%m-%d")))

    # ---------------------------------------------------------------- plumbing (= tests/test_rehearsal)
    def data(self, *p):
        return os.path.join(self.repo, "data", *p)

    def write_json(self, path, obj):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1)

    def configure(self, day):
        """The owner's three accounts for a fresh eval started today: LIT's 50K on Sim101 (live_model.json eval_start), ATLAS
        (account B) on Sim102, BLITZ (account C) on Sim103; yesterday's state files removed (every rehearsal day is a fresh
        eval)."""
        p = os.path.join(self.repo, "live_model.json")
        with open(p, encoding="utf-8") as fh:
            lm = json.load(fh)
        lm["lit_sizing"]["eval_start"] = day
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(lm, fh, indent=2)
        for f in ("live_state.json", "live_state_acctb.json", "live_state_acctc.json", "ninjatrader_state.json", "ninjatrader_state_acctb.json",
                  "ninjatrader_state_acctc.json", "blitz_state.json", "entry_pause.json"):
            try:
                os.remove(self.data(f))
            except OSError:
                pass
        self.write_json(self.data("account_b.json"), {"account_b": {"account": B_ACCT, "plan": "builder25k", "eval_start": day, "armed": False}})
        self.write_json(self.data("account_c.json"), {"account_c": {"account": C_ACCT, "plan": "builder25k", "eval_start": day, "armed": False}})

    def wait_idle(self, timeout=120):
        t_end = _real_time() + timeout
        while _real_time() < t_end:
            if self.vc.get(6) == 0 and self.vc.get(7) != 0:
                return True
            _real_sleep(0.003)
        return False

    def wait_poll(self, t, timeout=120):
        t_end = _real_time() + timeout
        while _real_time() < t_end:
            if self.vc.get(6) == 0:
                if self.vc.get(3) >= t - 1e-6 and self.vc.get(7) != 0:
                    return True
                if self.vc.get(7) > t + 1e-6 and self.vc.get(3) < t - 1e-6 and self.vc.get(7) - t < 31:
                    return True
            _real_sleep(0.003)
        return False

    def step(self, t, running=True):
        if running and not self.wait_idle():
            self.bugs.append(f"bot loop busy before {hm(t)}")
        m = int(t // 60 * 60)
        halted = self.feed.halt_t is not None and m - 60 >= self.feed.halt_t
        b = None if halted else self.feed.bar(m - 60)
        if b is not None and t % 60 < 30:
            self.nt.bar(*b)
        self.feed.publish(t)
        with self.nt.lock:
            self.nt.price = self.feed.price_at(min(t, self.feed.halt_t - 1) if self.feed.halt_t else t)
        self.vc.set(t)
        if running and not self.wait_poll(t):
            self.bugs.append(f"no poll finished after {hm(t)}")
            return False
        return True

    def c_blob(self):
        try:
            with open(self.data("live_state_acctc.json"), encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def b_blob(self):
        try:
            with open(self.data("live_state_acctb.json"), encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def owner_start(self, day):
        st = self.server.get(f"/api/next/botctl/status?account={LIT_ACCT}")
        t_end = _real_time() + 90
        while (st.get("selftest") or {}).get("ok") is None and _real_time() < t_end:
            _real_sleep(1.0)
            st = self.server.get(f"/api/next/botctl/status?account={LIT_ACCT}")
        pf = st.get("preflight") or {}
        bad = [f"{r['id']}={r['ok']} ({r.get('detail')})" for r in pf.get("rows") or [] if r.get("ok") is not True]
        check(f"{day} preflight on {LIT_ACCT} with BLITZ + ATLAS configured: every row green", pf.get("ok") and not bad, "; ".join(bad))
        n_polls = self.vc.get(4)
        res = self.server.post("/api/next/botctl/start", {"account": LIT_ACCT})
        t_end = _real_time() + 120
        while self.vc.get(4) <= n_polls and _real_time() < t_end:
            _real_sleep(0.01)
        check(f"{day} START on {LIT_ACCT} via Bot Control", res.get("ok") and res.get("sim") and not res.get("warning"), json.dumps(res)[:300])

    # ---------------------------------------------------------------- one session
    def run_day(self, day, kind, start, end, what):
        print(f"\n== {day} ({dt.date.fromisoformat(day):%a}) [{kind}]: {what}", flush=True)
        i = self.sessions.index(day)
        self.hist.cut(et_at(self.sessions[i - 2], 17, 0))
        self.configure(day)
        early = EARLY.get(kind)
        self.feed.halt_t = None if early is None else et_at(day, early // 60, early % 60)
        t0 = at_hm(day, start)
        t_end = at_hm(day, end)
        self.feed.reset(t0 + 2, self.nt_instrument("MNQ", dt.date.fromisoformat(day)))
        self.vc.set(t0 + 2)
        self.server.early = f"{day}={early}" if early else None
        self.server.start()
        n0 = len(self.nt.log)
        f0 = len(self.nt.fills)
        h0 = len(self.nt.hedge_viol)
        self.owner_start(day)
        exp0 = self.X.day(day)
        info = {"day": day, "kind": kind, "what": what, "bt": [self._bt_row(t) for t in exp0]}
        ev = {}
        if kind == "restart" and exp0:
            ev["restart"] = int(exp0[0]["entry_t"]) + 60 * RESTART_AFTER_MIN
        if kind == "refused":
            self.nt.refuse_c = 1
        if kind == "pause_kill" and len(exp0) >= 3:
            # the owner pauses new entries right after the first trade, until 2 minutes after the second one's entry
            ev["pause"] = (int(exp0[0]["exit_t"]) + 60, int(exp0[1]["entry_t"]) + 120)
            ev["kill"] = int(exp0[2]["entry_t"]) + 60 * KILL_AFTER_MIN
        running = True
        m = t0 + 60
        while m <= t_end:
            for off in (2, 32):
                t = m + off
                if off == 32 and not self.vc.get(5):
                    continue
                self.step(t, running=running)
                if ev.get("restart") and t >= ev["restart"]:
                    info["restart"] = self.do_restart(day, t)
                    ev.pop("restart")
                if ev.get("pause") and t >= ev["pause"][0]:
                    info["pause"] = self.do_pause(day, t, ev["pause"][1])
                    ev.pop("pause")
                if ev.get("kill") and t >= ev["kill"]:
                    info["kill"] = self.do_kill(day, t)
                    ev.pop("kill")
                    running = False
            m += 60
        _real_sleep(0.5)
        info.update(self.compare(day, kind, n0, f0, killed="kill" in info, restarted="restart" in info, early=early, t_end=t_end,
                                 pause=info.get("pause")))
        info["hedge_viol"] = self.nt.hedge_viol[h0:]
        check(f"{day} never long + short across the accounts: no NinjaTrader fill opened a position while another account "
              f"held the other side ({len(info['hedge_viol'])})", not info["hedge_viol"], json.dumps(info["hedge_viol"])[:400])
        info["heartbeat"] = self.check_heartbeat(day, killed="kill" in info)
        if "kill" not in info and info.get("trades"):
            # the Start page's go-live check over HTTP on the running bot (engine/blitz_preflight.py): after a routed Sim trade
            # BLITZ's own Sim session counts as the Sim test, so every line is green (the Sim account needs no arming)
            pf = self.server.get("/api/next/start/blitz/preflight?fresh=1") or {}
            bad = [f"{i.get('key')}={i.get('state')} ({i.get('detail')})" for i in pf.get("items") or [] if i.get("state") not in ("good", "info")]
            if early is not None:          # after the halt the feed is stale by design
                bad = [b for b in bad if not b.startswith("feed=")]
            if kind == "pass":             # a passed eval is red there on purpose: no new trade on it
                ev_l = [b for b in bad if b.startswith("eval=")]
                check(f"{day} go-live check after the pass: the eval line is red ({ev_l[:1]})", ev_l and "passed" in ev_l[0], bad)
                bad = [b for b in bad if not b.startswith("eval=") and not b.startswith("size=")]
            check(f"{day} GET /api/next/start/blitz/preflight on the running bot: {len(pf.get('items') or [])} lines, all green "
                  f"({pf.get('say')})", pf.get("items") and not bad, "; ".join(bad)[:500])
            info["preflight"] = [(i.get("key"), i.get("state"), str(i.get("detail"))[:120]) for i in pf.get("items") or []]
        try:
            lg = (self.server.get("/api/live/state") or {}).get("log") or []
            info["c_log"] = [f"{e.get('hm') or e.get('t')} {e.get('kind')} {e.get('text')}"[:300] for e in lg if "BLITZ" in str(e.get("text"))][:120]
        except Exception as e:
            info["c_log"] = [f"log not read: {e}"]
        if running:
            r = self.server.post("/api/next/botctl/stop")
            check(f"{day} STOP after the session", r.get("ok"), json.dumps(r)[:200])
        self.server.stop()
        with self.nt.lock:
            left = {f"{k[0]} {k[1]}": v[0] for k, v in self.nt.pos.items() if v[0]}
        check(f"{day} every account flat at NinjaTrader after the session", not left, str(left))
        self.rows.append(info)
        return info

    @staticmethod
    def _bt_row(t):
        return {k: (round(float(v), 4) if isinstance(v, float) else v) for k, v in t.items()
                if k in ("sig_t", "entry_t", "exit_t", "dir", "entry", "stop", "exit", "exit_kind", "risk_pts", "r", "pnl_pm")}

    # ---------------------------------------------------------------- events
    def do_restart(self, day, t):
        before = self.c_blob()
        n_mk = len([1 for _, ln in self.oif_lines() if ln.startswith(f"PLACE;{C_ACCT};") and ";MARKET;" in ln])
        self.server.stop()
        polls0 = self.vc.get(4)
        self.server.start()
        t_end = _real_time() + 120
        while self.vc.get(4) <= polls0 and _real_time() < t_end:
            _real_sleep(0.05)
        snap = self.server.get("/api/live/state") or {}
        after = self.c_blob()
        logs = [str(e.get("text")) for e in snap.get("log") or []]
        restored = next((x for x in logs if "restored: open BLITZ" in x), None)
        check(f"{day} RESTART {hm(t)}: server back, the Sim bot auto-resumed", snap.get("running"), json.dumps(snap.get("health") or {})[:200])
        check(f"{day} RESTART: account C restored its open BLITZ trade ({restored})", restored and before.get("open_t") is not None
              and after.get("open_t") == before.get("open_t"), f"before {before.get('open_t')} after {after.get('open_t')}")
        return {"t": hm(t), "open_t": before.get("open_t"), "restored": restored, "market_orders_before": n_mk}

    def do_pause(self, day, t, until):
        u = dt.datetime.fromtimestamp(until, ET).strftime("%H:%M")
        r = self.server.post("/api/next/pause", {"until": u})
        check(f"{day} owner PAUSE at {hm(t)} until {u} ET (POST /api/next/pause)", (r or {}).get("ok") is not False and "error" not in (r or {}),
              json.dumps(r)[:300])
        return {"t": int(t), "until": int(until), "res": r}

    def do_kill(self, day, t):
        n_lines = len(self.nt.log)
        res = self.server.post("/api/live/kill")
        _real_sleep(0.5)
        snap = self.server.get("/api/live/state") or {}
        lines = [ln for _, _, ls in self.nt.log[n_lines:] for ln in ls]
        with self.nt.lock:
            pos = {f"{k[0]}": v[0] for k, v in self.nt.pos.items()}
        check(f"{day} KILL {hm(t)}: the kill endpoint answered ok", res.get("ok"), json.dumps(res)[:200])
        check(f"{day} KILL: FLATTENEVERYTHING reached NinjaTrader", any(ln.startswith("FLATTENEVERYTHING") for ln in lines), str(lines)[:300])
        check(f"{day} KILL: every account flat (BLITZ's {C_ACCT} too)", all(q == 0 for q in pos.values()), str(pos))
        check(f"{day} KILL: bot stopped, kill flag on", not snap.get("running") and snap.get("kill"), f"running={snap.get('running')}")
        return {"t": int(t), "lines": lines[:6], "pos": pos}

    # ---------------------------------------------------------------- checks
    def oif_lines(self, a=None, z=None):
        return [(t, ln) for t, _, ls in self.nt.log for ln in ls if (a is None or t >= a) and (z is None or t < z)]

    def compare(self, day, kind, n0, f0, killed=False, restarted=False, early=None, pause=None, t_end=None):
        from engine.live import tick_px
        BZ = self.X.BZ
        blob = self.c_blob()
        bblob = self.b_blob()
        rows = [r for r in blob.get("rows") or [] if r.get("day") == day]
        masked = [r for r in rows if r.get("masked")]
        exp = [t for t in self.X.day(day, masked=[r["sig_t"] for r in masked]) if t_end is None or int(t["entry_t"]) < t_end]
        led = [r for r in blob.get("ledger") or [] if r.get("entry_t") and str(dt.datetime.fromtimestamp(int(r["entry_t"]), ET).date()) == day]
        ent = [r for r in led if r.get("side") in ("buy", "sell")]
        exits = [r for r in led if r.get("side") == "exit"]
        mods = [r for r in led if r.get("side") == "modify"]
        closes = {int(c[3]): c for c in blob.get("closes") or [] if len(c) > 3 and c[3] is not None}
        lines = [(t, name, ln) for t, name, ls in self.nt.log[n0:] for ln in ls]
        c_lines = [(t, ln) for t, name, ln in lines if "acctc" in name]       # CHANGE / CANCEL lines name no account (by order id)
        out = {"masked": [{"sig_t": r["sig_t"], "dir": r["dir"], "why": r.get("skip")} for r in masked],
               "expected": [self._bt_row(t) for t in exp],
               "routed": [{k: r.get(k) for k in ("t", "side", "qty", "stop", "target", "entry", "entry_t", "reason", "pnl", "exit_t")} for r in led],
               "oif_c": [f"{hm(t)} {ln}" for t, ln in c_lines]}
        # 1. account C's orders only on its own account; nobody else's on it
        wrong = [ln for t, name, ln in lines if ("acctc" in name and ln.split(";")[1] not in ("", C_ACCT)) or ("acctc" not in name and f";{C_ACCT};" in ln)]
        check(f"{day} account C's order files (tag acctc_) name only {C_ACCT}, and only they do ({len(c_lines)} lines)", not wrong, str(wrong[:3]))
        # 2. every mask names LIT / ATLAS the other way, and the other account really was there
        for r in masked:
            why = str(r.get("skip") or "")
            ok = why.startswith("no hedging") and ("LIT" in why or "ATLAS" in why)
            check(f"{day} BLITZ {r.get('side')} candidate at the {hm(int(r['sig_t']) + 60)} close masked: {why[:120]}", ok, why)
        if kind in ("lit_mask",):
            check(f"{day} at least one BLITZ candidate masked by LIT ({len(masked)})", any("LIT" in str(r.get("skip")) for r in masked),
                  json.dumps(rows)[:400])
        # 3. the routed trades = the expected trades, one for one
        blocked = {}
        if kind == "refused" and self.nt.refused:
            blocked[int(exp[0]["entry_t"])] = "refused"
        if pause:
            for t in exp:
                if pause["t"] <= int(t["entry_t"]) < pause["until"]:
                    blocked[int(t["entry_t"])] = "paused"
        if early is not None:
            ec_t = et_at(day, early // 60, early % 60)
            for t in exp:
                if int(t["entry_t"]) >= ec_t - 15 * 60:
                    blocked[int(t["entry_t"])] = "early close: last 15 min"
        # the eval's own stops (a fresh Builder 25K): +$1,500 = passed (no new trade), -$600 today = the soft daily loss lock
        cum_x = 0.0
        for t in exp:
            if int(t["entry_t"]) in blocked:
                continue
            if cum_x >= 1500.0:
                blocked[int(t["entry_t"])] = "eval passed"
            elif cum_x <= -600.0:
                blocked[int(t["entry_t"])] = "daily loss"
            else:
                cum_x += expected_qty(t["risk_pts"], cum_x) * float(t["pnl_pm"])
        want = [t for t in exp if int(t["entry_t"]) not in blocked]
        kill_t = None
        if killed:
            kill_t = next((int(r["t"]) for r in exits if r.get("reason") == "KILL SWITCH"), None)
            want = [t for t in want if kill_t is None or int(t["entry_t"]) <= kill_t]
        got = {int(r["entry_t"]): r for r in ent}
        want_t = sorted([int(t["entry_t"]) for t in want] + [k for k, v in blocked.items() if v == "refused"])
        check(f"{day} routed BLITZ entries = the backtest's ({len(want)} expected, {len(blocked)} blocked on purpose: "
              f"{sorted(set(blocked.values())) or '-'}; {len(masked)} masked by no hedging)", sorted(got) == want_t and len(ent) == len(got),
              f"routed {[hm(x) for x in sorted(got)]} expected {[hm(x) for x in want_t]} blocked {[hm(x) for x in blocked]}")
        for et_, why in blocked.items():
            r = got.get(et_)
            if why == "refused":
                ok = r is not None and (r.get("result") or {}).get("ok") is False and et_ not in closes
                check(f"{day} {hm(et_)} entry REFUSED by NinjaTrader: routed once, NOT booked, C flat; push 'order NOT placed'",
                      ok and f"acctc:notplaced:{et_}" in (blob.get("notified") or []) and blob.get("open_t") != et_, json.dumps(r)[:300])
                left = [ln for t, ln in c_lines if t >= et_ and ln.startswith("PLACE") and (";STOPMARKET;" in ln or ";LIMIT;" in ln)
                        and t < et_ + 120]
                with self.nt.lock:
                    work = [k for k, o in self.nt.orders.items() if o.get("account") == C_ACCT and o.get("state") in ("WORKING", "ACCEPTED")]
                check(f"{day} refused entry: no stop / target left working at NinjaTrader for it ({len(left)} bracket lines, {len(work)} working)",
                      not work, str(left[:2]))
            elif why in ("eval passed", "daily loss"):
                rw = next((x for x in rows if int(x.get("entry_t") or 0) == et_), {})
                pushed = [k for k in blob.get("notified") or [] if k.startswith("acctc:passed:")] if why == "eval passed" else \
                    ([f"lock {(blob.get('lock') or {}).get('day')}"] if (blob.get("lock") or {}).get("day") == day else [])
                check(f"{day} {hm(et_)} BLITZ signal not routed: {why} ({str(rw.get('skip'))[:90]}); {pushed[:1]}",
                      r is None and (("passed" in str(rw.get("skip"))) if why == "eval passed" else ("locked" in str(rw.get("skip"))))
                      and len(pushed) == 1, json.dumps(rw)[:300])
            elif why == "paused":
                rw = next((x for x in rows if int(x.get("entry_t") or 0) == et_), {})
                check(f"{day} {hm(et_)} BLITZ entry not routed while the owner's pause runs ({str(rw.get('skip'))[:80]})",
                      r is None and "paused" in str(rw.get("skip")).lower(), json.dumps(rw)[:300])
            else:
                rw = next((x for x in rows if int(x.get("entry_t") or 0) == et_), {})
                check(f"{day} {hm(et_)} BLITZ signal not entered: {str(rw.get('skip'))[:100]}", r is None, json.dumps(rw)[:300])
        cum, pnl_sum, trades = 0.0, 0.0, []
        for t in exp:
            et_ = int(t["entry_t"])
            if et_ in blocked:
                continue
            e = got.get(et_)
            if e is None:
                continue
            D = int(t["dir"])
            q = expected_qty(t["risk_pts"], cum)
            ws = tick_px(t["stop"], D)
            wt = tick_px(float(t["entry"]) + D * BZ.TGT_R * max(float(t["risk_pts"]), TICK), D, target=True)
            lag = int(e["t"]) - et_
            check(f"{day} {hm(et_)} {('BUY' if D == 1 else 'SELL')} {e['qty']} routed {lag} s after the open = backtest entry "
                  f"(size {q}: 40% of ${1000 + cum:,.0f} room, risk {t['risk_pts']:.2f} pts)",
                  e["side"] == ("buy" if D == 1 else "sell") and int(e["qty"]) == q and 0 <= lag <= LIMIT_S, json.dumps(e)[:300])
            check(f"{day} {hm(et_)} stop {e['stop']} (1.5 x 5m ATR) / OCO target {e['target']} (20R) = backtest {ws} / {wt}",
                  abs(float(e["stop"]) - ws) < 1e-9 and abs(float(e["target"]) - wt) < 1e-9)
            mk = [(tt, ln) for tt, ln in c_lines if ln.startswith("PLACE") and ";MARKET;" in ln and et_ <= tt < et_ + 60]
            fills = [x for x in self.nt.fills[f0:] if x[2] == "MARKET" and et_ <= x[0] < et_ + 60 and
                     (self.nt.orders.get(x[1]) or {}).get("account") == C_ACCT and x[3] == ("BUY" if D == 1 else "SELL")]
            fp = fills[0][5] if fills else None
            n_mk = len(mk)
            check(f"{day} {hm(et_)} NinjaTrader: one MARKET {q} on {C_ACCT}, filled {fp} = backtest fill {t['entry']}",
                  n_mk == 1 and int(mk[0][1].split(";")[4]) == q and fp is not None and abs(fp - float(t["entry"])) < 1e-9,
                  f"{mk[:2]} fills {fills[:2]}")
            br = [ln for tt, ln in c_lines if ln.startswith("PLACE") and et_ <= tt < et_ + 60 and (";STOPMARKET;" in ln or ";LIMIT;" in ln)]
            sl = [ln for ln in br if ";STOPMARKET;" in ln]
            tl = [ln for ln in br if ";LIMIT;" in ln]
            check(f"{day} {hm(et_)} bracket at NinjaTrader: STOPMARKET {ws} + LIMIT {wt}, qty {q}, one OCO",
                  sl and tl and float(sl[0].split(";")[7]) == ws and float(tl[0].split(";")[6]) == wt and int(sl[0].split(";")[4]) == q
                  and sl[0].split(";")[9] == tl[0].split(";")[9], f"{sl[:1]} {tl[:1]}")
            # trail: every CHANGE tighter than the one before, = the model's trailed stops
            my = [r for r in mods if int(r["entry_t"]) == et_]
            stops = [float(r["stop"]) for r in my if (r.get("result") or {}).get("ok")]
            tight = all(D * (b - a) > 0 for a, b in zip([ws] + stops, stops))
            want_tr, last = [], ws
            hedge_x = next((r for r in exits if int(r["entry_t"]) == et_ and r.get("reason") in ("HEDGE", "KILL SWITCH")), None)
            for (tc, s) in self.X.trail_stops(t):
                if hedge_x is not None and tc > int(hedge_x["t"]):
                    break
                if kind.startswith("early") and tc > et_at(day, early // 60, early % 60) - 5 * 60:
                    break
                s2 = tick_px(s, D)
                if D * (s2 - last) > 0:
                    want_tr.append(s2)
                    last = s2
            chg = [ln for tt, ln in c_lines if ln.startswith("CHANGE") and et_ <= tt <= int(t["exit_t"]) + 60]
            it = iter(want_tr)
            subseq = all(any(s == w for w in it) for s in stops)     # in the model's order, none invented
            skipped = [w for w in want_tr if w not in stops]
            final_ok = (not want_tr and not stops) or (stops and want_tr and stops[-1] == want_tr[-1])
            check(f"{day} {hm(et_)} trail: {len(stops)} stop CHANGEs at NinjaTrader ({len(chg)} lines), each tighter than the last, "
                  f"all the model's trailed stops, the last = the model's last ({want_tr[-1] if want_tr else '-'})"
                  + (f"; {len(skipped)} intermediate step(s) folded into the next minute's" if skipped else ""),
                  tight and subseq and final_ok and len(chg) == len(stops), f"routed {stops} model {want_tr}")
            # the exit
            x = [r for r in exits if int(r["entry_t"]) == et_]
            c = closes.get(et_)
            if hedge_x is not None:
                xr = hedge_x
                bar = self.feed.bar(int(xr["t"]) // 60 * 60)
                pv = q * (D * (float(bar[0]) - D * TICK - float(t["entry"])) * 2.0 - 1.90) if bar else None
                # the market at that minute's open; a HEDGE books ATLAS's / LIT's entry price as BLITZ's exit (1 tick either way)
                check(f"{day} {hm(et_)} closed by {xr.get('reason')} at {hm(xr['t'])} (market): booked ${c and c[2]} = {q} x the market "
                      f"(${pv and round(pv, 2)}, within 1 tick a micro)", c is not None and pv is not None
                      and abs(float(c[2]) - round(pv, 2)) <= q * TICK * 2.0 + 0.011, json.dumps(xr)[:300])
                pnl = float(c[2]) if c else 0.0
            elif early is not None and int(t["exit_t"]) > et_at(day, early // 60, early % 60) - 5 * 60:
                fx = next((r for r in x if r.get("reason") == "TIME"), None)
                flat_t = et_at(day, early // 60, early % 60) - 5 * 60
                cl = [tt for tt, ln in c_lines if ln.startswith("CLOSEPOSITION") and tt >= et_]
                check(f"{day} {hm(et_)} early close: flattened at {hm(fx and fx['t'])} (CLOSEPOSITION {hm(cl[0]) if cl else None}), "
                      f"5 minutes before the {early // 60:02d}:{early % 60:02d} halt", fx is not None and cl and 0 <= cl[0] - flat_t <= LIMIT_S
                      and c is not None, json.dumps(x)[:300])
                pnl = float(c[2]) if c else 0.0
            else:
                want_r = EXIT_MAP.get(t["exit_kind"], t["exit_kind"].upper())
                xx = x[0] if x else {}
                check(f"{day} {hm(et_)} exit {xx.get('reason')} at {hm(xx.get('exit_t'))} = backtest {t['exit_kind']} {hm(t['exit_t'])}",
                      len(x) >= 1 and xx.get("reason") == want_r and int(xx.get("exit_t") or 0) == int(t["exit_t"]), json.dumps(x)[:300])
                want_usd = round(q * float(t["pnl_pm"]), 2)
                check(f"{day} {hm(et_)} booked ${c and c[2]} = {q} x the backtest's ${t['pnl_pm']:.2f} a micro (${want_usd})",
                      c is not None and abs(float(c[2]) - want_usd) < 0.011, str(c))
                if want_r == "TIME":
                    cl = [tt for tt, ln in c_lines if ln.startswith("CLOSEPOSITION") and int(t["exit_t"]) - 60 <= tt <= int(t["exit_t"]) + 60]
                    check(f"{day} {hm(et_)} {'15:55 flat' if t['exit_kind'] == 'flat' else '30-bar time exit'}: CLOSEPOSITION "
                          f"{(cl[0] - int(t['exit_t'])) if cl else None} s after the bar close", cl and 0 <= cl[0] - int(t["exit_t"]) <= LIMIT_S)
                pnl = float(c[2]) if c else 0.0
            # the broker's own P&L (fills) next to the booked one
            xs = [y for y in self.nt.fills[f0:] if (self.nt.orders.get(y[1]) or {}).get("account") == C_ACCT and y[3] == ("SELL" if D == 1 else "BUY")
                  and et_ <= y[0] <= int(t["exit_t"]) + 120]
            bp = None
            if fp is not None and xs:
                qq = sum(y[4] for y in xs)
                xp = sum(y[4] * y[5] for y in xs) / qq
                bp = round(qq * ((xp - fp) * D * 2.0 - 1.90), 2)
            trades.append({"entry_t": et_, "entry": hm(et_), "dir": D, "qty": q, "exit_kind": (hedge_x or {}).get("reason") or t["exit_kind"], "bt_exit": t["exit_kind"], "booked": pnl, "broker": bp,
                           "bt_usd": round(q * float(t["pnl_pm"]), 2), "changes": len(stops)})
            cum += pnl
            pnl_sum += pnl
        out["trades"] = trades
        out["booked"] = round(pnl_sum, 2)
        errs = [r for r in led if (r.get("result") or {}).get("ok") is False and not (kind == "refused" and int(r["entry_t"]) in blocked)]
        check(f"{day} every routed BLITZ order accepted", not errs, json.dumps([{k: r.get(k) for k in ("side", "reason", "result")} for r in errs])[:400])
        check(f"{day} fake NinjaTrader: every OIF line valid", not self.nt.errors, str(self.nt.errors[-3:]))
        # 4. what the other accounts did (ATLAS / LIT) on the hedge days
        if kind in ("atlas_opp", "atlas_same"):
            b_ent = [r for r in bblob.get("ledger") or [] if r.get("side") in ("buy", "sell") and r.get("entry_t")
                     and str(dt.datetime.fromtimestamp(int(r["entry_t"]), ET).date()) == day]
            hx = [r for r in exits if r.get("reason") == "HEDGE"]
            check(f"{day} ATLAS (account B) entered on {B_ACCT} ({len(b_ent)}: {[(hm(r['entry_t']), r['side']) for r in b_ent]})", b_ent)
            check(f"{day} BLITZ closed by HEDGE before ATLAS's opposite entry ({len(hx)})", hx, json.dumps(exits)[:300])
            if hx and b_ent:
                cp = [tt for tt, ln in c_lines if ln.startswith("CLOSEPOSITION") and tt >= int(hx[0]["t"]) - 5]
                bp_ = [tt for tt, _, ln in lines if ln.startswith(f"PLACE;{B_ACCT};") and ";MARKET;" in ln and tt >= int(b_ent[0]["entry_t"])]
                check(f"{day} order at NinjaTrader: BLITZ's CLOSEPOSITION ({hm(cp[0]) if cp else None}) before ATLAS's MARKET "
                      f"({hm(bp_[0]) if bp_ else None})", cp and bp_ and cp[0] <= bp_[0], f"{cp[:2]} {bp_[:2]}")
        out["b_entries"] = [(hm(r["entry_t"]), r.get("side"), r.get("qty")) for r in bblob.get("ledger") or [] if r.get("side") in ("buy", "sell")]
        out["c_state"] = {"open_t": blob.get("open_t"), "notified": (blob.get("notified") or [])[-12:]}
        return out

    def check_heartbeat(self, day, killed=False):
        p = os.path.join(self.repo, "logs", "heartbeat_last.json")
        t_end, hb = _real_time() + 60, None
        while _real_time() < t_end:
            try:
                hb = json.load(open(p, encoding="utf-8"))
                if abs(float((hb.get("payload") or {}).get("t") or 0) - self.vc.now()) < 240:
                    break
            except Exception:
                pass
            _real_sleep(1)
        pl = (hb or {}).get("payload") or {}
        ac = pl.get("account_c") or {}
        check(f"{day} heartbeat carries account C: {ac.get('label')} {ac.get('real')} ({ac.get('kind')}), eval session "
              f"{(ac.get('eval') or {}).get('session')}, {len(ac.get('closed') or [])} closed trades",
              ac.get("account") == C_ACCT and ac.get("real") == "SIM" and (ac.get("eval") or {}).get("session") == 1,
              json.dumps(ac)[:300])
        return {"label": ac.get("label"), "real": ac.get("real"), "state": (ac.get("state") or {}).get("text"), "eval": ac.get("eval"),
                "scorecard": {k: (ac.get("scorecard") or {}).get(k) for k in ("n", "win_pct", "avg_r", "usd", "status")}}

    def run(self):
        self.resp.start()
        try:
            for day, kind, start, end, what in self.days:
                try:
                    self.run_day(day, kind, start, end, what)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    check(f"{day} rehearsal day ran", False, f"{e.__class__.__name__}: {e}")
                    try:
                        if self.server:
                            self.server.stop()
                    except Exception:
                        pass
        finally:
            self.resp.stop.set()
        tb = []
        for n in range(1, (self.server.n if self.server else 0) + 1):
            try:
                txt = open(os.path.join(self.base, f"server_{n}.log"), encoding="utf-8", errors="replace").read()
                tb += [ln for ln in txt.splitlines() if "Traceback" in ln]
            except OSError:
                pass
        check("server logs: no traceback", not tb, "\n".join(tb[:5]))


def summary(rows, bugs, out=None):
    print("\n== BLITZ rehearsal results")
    print(f"{'day':<11} {'kind':<11} {'bt':>3} {'routed':>6} {'masked':>6}  booked $   broker $   trades")
    for r in rows:
        tr = r.get("trades") or []
        bk = sum((x.get("broker") or 0) for x in tr)
        print(f"{r['day']:<11} {r['kind']:<11} {len(r.get('bt') or []):>3} {len(tr):>6} {len(r.get('masked') or []):>6}  "
              f"{r.get('booked', 0):>8,.2f} {bk:>9,.2f}   " + ", ".join(f"{x['entry']} {'L' if x['dir'] == 1 else 'S'}{x['qty']} {x['exit_kind']} "
                                                                   f"${x['booked']:+.0f}" for x in tr))
    n_ok = sum(1 for x in RESULTS if x["ok"])
    print(f"\n{n_ok}/{len(RESULTS)} checks passed" + (f"; loop notes: {bugs[:5]}" if bugs else ""))
    out = out or OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"t": int(_real_time()), "passed": n_ok, "total": len(RESULTS), "checks": RESULTS, "days": rows, "bugs": bugs}, fh,
                  indent=1, default=str)
    print("->", out)
    return n_ok == len(RESULTS)


def main(argv):
    if argv[:1] == ["--serve"]:
        return serve(*argv[1:4])
    days = DAYS
    jobs, part = 1, None
    summ = next((a.split("=", 1)[1] for a in argv if a.startswith("--summary=")), None)
    if summ:                                   # re-summarize a parts folder (a day re-run into it with --part=<folder>/<day>_<kind>.json)
        RESULTS.clear()
        rows, bugs = [], []
        for f in sorted(os.listdir(summ)):
            if f.endswith(".json"):
                j = json.load(open(os.path.join(summ, f), encoding="utf-8"))
                RESULTS.extend(j["checks"])
                rows += j["days"]
                bugs += j["bugs"]
        return 0 if summary(sorted(rows, key=lambda r: r["day"]), bugs) else 1
    for a in argv:
        if a.startswith("--days="):
            want = a.split("=", 1)[1].split(",")
            days = [d for d in DAYS if d[0] in want or d[1] in want]
        if a.startswith("--jobs="):
            jobs = int(a.split("=", 1)[1])
        if a.startswith("--part="):
            part = a.split("=", 1)[1]
    if jobs > 1:
        return run_parallel(days, jobs, argv)
    t0 = _real_time()
    rh = Rehearsal(days, keep="--keep" in argv)
    try:
        rh.run()
        ok = summary(rh.rows, rh.bugs, out=part)
    finally:
        if "--keep" not in argv:
            shutil.rmtree(rh.base, ignore_errors=True)
        else:
            print("sandbox kept:", rh.base)
    print(f"{_real_time() - t0:.0f} s")
    return 0 if ok else 1


def run_parallel(days, jobs, argv):
    tmp = tempfile.mkdtemp(prefix="le_rh_blitz_parts_")
    procs, done = [], []
    queue = list(days)
    keep = [a for a in argv if a == "--keep"]
    t0 = _real_time()
    while queue or procs:
        while queue and len(procs) < jobs:
            d = queue.pop(0)
            part = os.path.join(tmp, f"{d[0]}_{d[1]}.json")
            logp = os.path.join(tmp, f"{d[0]}_{d[1]}.log")
            p = subprocess.Popen([sys.executable, "-X", "utf8", "-m", "tests.test_rehearsal_blitz", f"--days={d[1]}", f"--part={part}", *keep],
                                 cwd=ROOT, stdout=open(logp, "w", encoding="utf-8"), stderr=subprocess.STDOUT)
            procs.append((p, d, part, logp))
            print(f"started {d[0]} [{d[1]}] -> {logp}", flush=True)
        for x in list(procs):
            if x[0].poll() is not None:
                procs.remove(x)
                done.append(x)
                txt = open(x[3], encoding="utf-8", errors="replace").read()
                print(f"\n---- {x[1][0]} [{x[1][1]}] (exit {x[0].returncode}, {_real_time() - t0:.0f} s)\n"
                      + "\n".join(ln for ln in txt.splitlines() if "[FAIL]" in ln or "[PASS]" in ln), flush=True)
        _real_sleep(2)
    rows, bugs = [], []
    RESULTS.clear()
    for _, d, part, logp in sorted(done, key=lambda x: x[1][0]):
        try:
            j = json.load(open(part, encoding="utf-8"))
        except Exception as e:
            RESULTS.append({"name": f"{d[0]} [{d[1]}] rehearsal process", "ok": False, "detail": f"no result ({e}); see {logp}"})
            continue
        RESULTS.extend(j["checks"])
        rows += j["days"]
        bugs += j["bugs"]
    ok = summary(rows, bugs)
    print(f"parts: {tmp}  ({_real_time() - t0:.0f} s)")
    if ok and "--keep" not in argv:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
