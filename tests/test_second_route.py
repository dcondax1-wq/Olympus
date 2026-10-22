"""Routed second strategies (second_model.json "route": true) on LIT's account through the PC bot. Sim / fake NinjaTrader
only (engine/ninjatrader._FakeNT on a temp folder, account Sim101); nothing is ever armed for a real account and
second_model.json is never edited by this test (the start cfg "second_route" switches routing on for the harness).

    python -X utf8 -m tests.test_second_route            # everything (~10-15 min)
    python -X utf8 -m tests.test_second_route --quick    # a + unit checks + one EMA day + d (~3 min)
    python -X utf8 -m tests.test_second_route --suites   # also run the other suites of (f)

 a. route off = today: second_model.json ships "route": false everywhere; tests.test_lit_live --days --bot (120/120,
    LiveBot entries 2/2 exits 2/2) and a LiveBot day with EMA signals but routing off: 0 second-strategy routes.
 b. route on for ema_lon_vix, LiveBot + fake NinjaTrader (Sim101) over 2026 days with EMA trades, incl. days where LIT and
    EMA both trade: each EMA entry written within seconds of its 5m open (side, micros, stop, target = the research
    trade), its breakeven move (CHANGE of the stop to entry + 1.25), its exit (reason, $); LIT's trades unchanged; LIT
    first (no EMA entry while LIT is in a trade; an open EMA trade is closed at market when LIT enters); never 2 positions;
    max 2 entries a day (unit checks on engine/guards.dup_problem too); eval-safe sizing (engine/sizing.second_qty).
 c. one day each for macd_sweep (its 15-minute cut) and sr_nyreclaim (its 15-minute cut).
 d. an exception in the second-strategy code never blocks or delays LIT (LIT's routes identical, same delay).
 e. restart mid-trade: a new LiveBot on the same live_state.json / NinjaTrader state finds the open second-strategy
    position, manages it to its exit, and the reconcile guard never flattens it as a manual trade.
 f. --suites: engine.ninjatrader --selftest, tests.test_guards, test_eval_lifecycle, test_second --quick, test_pcdash_api,
    test_alerts_plus, test_no_yahoo.
Results -> research/second/route_check.json.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import pandas as pd  # noqa: E402

from engine import live  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402
from engine import second  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.live import tick_px  # noqa: E402
from tests.test_lit_timing import Clock  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "second", "route_check.json")
RESULTS = []
REF_FILE = {"ema_lon_vix": "research/second/ema_best.json", "macd_sweep": "research/second/md_best.json",
            "sr_nyreclaim": "research/second/sr_best.json"}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:900]}"), flush=True)


def hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M:%S")


def at(d, hh, mm):
    day = dt.date.fromisoformat(d)
    if hh >= 18:
        day -= dt.timedelta(days=1)
    return int(dt.datetime.combine(day, dt.time(hh, mm), ET).timestamp())


def kind_reason(k):
    k = str(k).upper()
    return "TIME" if k in ("FLAT", "EOD") else k


class Ref:
    def __init__(self):
        self.lit_p = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
        r = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
        self.lit = collections.defaultdict(list)
        for a in r["trades"]:
            t = dict(zip(r["trade_cols"], a))
            self.lit[t["day"]].append(t)
        self.sec = {k: collections.defaultdict(list) for k in REF_FILE}
        for k, f in REF_FILE.items():
            for t in json.load(open(os.path.join(ROOT, f), encoding="utf-8"))["trades"]:
                if "2026-01-01" <= t["day"] <= "2026-10-16":
                    self.sec[k][t["day"]].append(t)


class Harness:
    """LiveBot (engine/live.py, model LIT) + fake NinjaTrader (Sim101), polled on the PC bot's schedule (2 s after each
    minute / 5m close) with a clock that runs on during each poll; bars appear as they close, the 1m feed shows the
    minute that has just started from its open (LE_BarFeed's open file)."""

    def __init__(self, ref, lm_extra=None):
        from tests.test_live_dryrun import Replay
        self.ref = ref
        os.environ["LE_LIVE_MODEL"] = json.dumps({"model": "lit", "sym": "NQ", "label": "LIT + second route test", "lit": ref.lit_p,
                                                  "params": {"risk_usd": 800, "risk_ref_stop": 20.0, "max_micros": 40},
                                                  **(lm_extra or {})})
        for k in (nt.LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER"):
            os.environ.pop(k, None)
        self.rp = rp = Replay()
        df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        rp.frames[("NQ", "1m")] = df1[df1["time"] >= at("2026-07-01", 18, 0) - 70 * 86400].reset_index(drop=True)
        self.o1 = dict(zip(df1["time"].astype("int64"), df1["open"].astype(float)))
        self.c1 = dict(zip(df1["time"].astype("int64"), df1["close"].astype(float)))
        self.clock = clock = Clock()

        def forming_1m(sym, interval, period="5d"):
            t = int(clock()) - int(clock()) % 60
            if sym == "NQ" and interval == "1m" and t in self.o1:
                o = self.o1[t]
                return pd.DataFrame([{"time": t, "open": o, "high": o, "low": o, "close": o, "volume": 0.0}])
            return pd.DataFrame()
        rp.recent_hook = forming_1m
        rp.install_globals()
        self.tmp = tempfile.mkdtemp(prefix="le_second_route_")

    def close(self):
        os.environ.pop("LE_LIVE_MODEL", None)
        self.rp.cleanup()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bot(self, tag, route, start_t, fake=None, cfg_extra=None):
        d = os.path.join(self.tmp, tag)
        folder = os.path.join(d, "NinjaTrader 8")
        fake = fake or nt._FakeNT(folder, price=25000.0)
        self.rp.now = int(start_t)
        self.clock.base, self.clock.running = float(start_t), False
        b = live.LiveBot()
        b.clock = self.clock
        b.read_hist, b.fetch_recent = self.rp.read_hist, self.rp.fetch_recent
        b.state_path = os.path.join(d, "live_state.json")
        b._remember = lambda *a_, **kw: None
        r = b.start({"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "nt_folder": folder, "nt_account": "Sim101",
                     "model": "lit", "model_params": self.ref.lit_p, "params": {"max_micros": 40, "flat_mod": 955},
                     "nt_state_path": os.path.join(d, "nt_state.json"), "nt_audit_log": os.path.join(d, "oif.log"),
                     "second_route": list(route), **(cfg_extra or {})}, spawn=False)
        assert r.get("ok"), r
        ad = b.adapter
        ad.clock = self.clock
        ad._alert_fn = lambda *a_, **kw: None
        clock = self.clock

        def nt_sleep(s_, fake=fake):
            fake.process()
            clock.base += s_
        ad._sleep = nt_sleep
        return b, fake

    def times(self, day, keys, extra=()):
        """Poll times: every 5m close (+2 s) 01:50-16:10, every minute (+2 s) from 10 min before to 5 min after each LIT /
        second-strategy trade of the day (the PC bot polls each minute: 1m CISD entries, 15-minute cuts)."""
        a, z = at(day, 1, 50), at(day, 16, 10)
        T = set(range(a, z + 1, 300))
        trs = list(self.ref.lit.get(day, [])) + [t for k in keys for t in self.ref.sec[k].get(day, [])] + list(extra)
        for t in trs:
            T |= set(range(int(t["entry_t"]) - 600, int(t.get("exit_t") or t["entry_t"]) + 301, 60))
        return sorted(x + 2 for x in T if a <= x <= z)

    def run(self, b, fake, wakes, errors, on_poll=None):
        legs_max = 0
        for w in wakes:
            self.rp.now = int(w)
            self.clock.base, self.clock.t0, self.clock.running = float(w), self.clock.src(), True
            last = int(w) - int(w) % 60 - 60
            if last in self.c1:
                fake.move(self.c1[last])
            try:
                b.poll_once()
            except Exception as e:
                errors.append(f"{hm(w)} {e.__class__.__name__}: {e}")
            self.clock.running = False
            n_open = sum(1 for q, _ in fake.pos.values() if q)
            legs_max = max(legs_max, n_open, sum(1 for lg in b.adapter.legs if lg["status"] in nt.OPEN_STATUSES))
            if on_poll:
                on_poll(b, w)
        return legs_max


def ledger_rows(b):
    return [r for r in b.ledger if r.get("side") in ("buy", "sell", "exit", "modify")]


def one_position(b):
    """From the ledger: no entry is sent while another routed entry is still open."""
    open_, bad = None, []
    for r in b.ledger:
        if r.get("side") in ("buy", "sell"):
            if open_ is not None:
                bad.append((hm(r["t"]), "entry while", hm(open_)))
            open_ = r["entry_t"]
        elif r.get("side") == "exit" and r.get("entry_t") == open_:
            open_ = None
    return bad


def second_expect(ref, key, day, lit_day):
    """The research trades of `key` on `day` and what the account rule does with each: routed (maybe closed when LIT
    enters) or skipped because LIT is in a trade / has an armed setup (the bot logs why)."""
    from tools.second_route_eval import lit_busy_at
    out = []
    for u in ref.sec[key].get(day, []):
        et_ = int(u["entry_t"])
        in_lit = any(int(t["entry_t"]) <= et_ < int(t["exit_t"]) for t in lit_day)
        busy = "LIT is in a trade" if in_lit else lit_busy_at(et_ + 2)     # LIT's own live loop at the EMA bar's open
        pre = next((int(t["entry_t"]) for t in lit_day if et_ < int(t["entry_t"]) < int(u["exit_t"])), None)
        out.append({**u, "in_lit": bool(busy), "busy": busy, "pre": pre})
    return out


def day_check(H, key, day, label, keys_route=None, cfg_extra=None, qty_fn=None):
    """One session: the bot routes LIT and `key`; checks every research trade of both against the ledger / order files."""
    keys_route = keys_route if keys_route is not None else [key]
    b, fake = H.bot(f"{key}_{day}", keys_route, at(day, 1, 45), cfg_extra=cfg_extra)
    errors = []
    t0 = time.time()
    mx = H.run(b, fake, H.times(day, [key]), errors)
    L = H.ref.lit.get(day, [])
    led = b.ledger
    ent = {r["entry_t"]: r for r in led if r.get("side") in ("buy", "sell")}
    exi = {r["entry_t"]: r for r in led if r.get("side") == "exit" and r.get("entry_t")}
    mods = collections.defaultdict(list)
    for r in led:
        if r.get("side") == "modify":
            mods[r["entry_t"]].append(r)
    # LIT unchanged: every lit_live trade routed once and exited with its reason
    lit_ok = all(int(t["entry_t"]) in ent and not ent[int(t["entry_t"])].get("src")
                 and ent[int(t["entry_t"])]["side"] == ("buy" if t["dir"] == 1 else "sell")
                 and int(t["entry_t"]) in exi and exi[int(t["entry_t"])]["reason"] == kind_reason(t["exit"]) for t in L)
    check(f"{label}: LIT's {len(L)} trade(s) routed and exited as run lit_live", lit_ok,
          [(hm(t["entry_t"]), t["exit"], ent.get(int(t["entry_t"])), exi.get(int(t["entry_t"]))) for t in L])
    rows = []
    for u in second_expect(H.ref, key, day, L):
        et_, d = int(u["entry_t"]), int(u["dir"])
        e = ent.get(et_)
        if u["in_lit"]:
            check(f"{label}: {key} {hm(et_)} NOT routed: {u['busy']} (LIT first)", e is None and any(
                "NOT routed" in x["text"] and u["busy"] in x["text"] for x in b.log),
                [x["text"] for x in b.log if "NOT routed" in x["text"] or "Second" in x["text"]][:6])
            rows.append({"entry": hm(et_), "routed": False, "why": u["busy"]})
            continue
        q_want = qty_fn(u) if qty_fn else SZ.second_qty(float(abs(u["entry"] - u["stop"])), 500.0)["qty"]
        okE = e is not None and e.get("src") == key and e["side"] == ("buy" if d == 1 else "sell") and int(e["qty"]) == int(q_want) \
            and abs(float(e["stop"]) - tick_px(u["stop"], d)) < 1e-6 and abs(float(e["target"]) - tick_px(u["target"], d, target=True)) < 1e-6
        delay = round(float(e["t"]) - et_, 2) if e else None
        check(f"{label}: {key} {hm(et_)} entry routed like the research trade (side, {q_want} micros, stop, target) "
              f"{delay} s after its 5m open", okE and delay is not None and delay <= 10.0,
              (e and {k: e.get(k) for k in ("t", "side", "qty", "stop", "target", "src", "result")}, u, q_want))
        x = exi.get(et_)
        if u["pre"]:
            okX = x is not None and x["reason"] == "LIT PRIORITY" and abs(float(x["t"]) - u["pre"]) <= 10 and \
                ent.get(u["pre"]) is not None and float(ent[u["pre"]]["t"]) >= float(x["t"])
            check(f"{label}: {key} {hm(et_)} closed at market when LIT entered {hm(u['pre'])}, before LIT's order", okX,
                  (x, ent.get(u["pre"])))
        else:
            want = kind_reason(u["exit_kind"])
            usd = float(u.get("pnl_usd") if u.get("pnl_usd") is not None else u.get("pnl"))
            pnl_want = round(usd * int(q_want) / int(u["qty"]), 2)
            okX = x is not None and x["reason"] == want and abs(float(x.get("pnl") or 0) - pnl_want) <= max(0.05, 0.03 * int(q_want))
            check(f"{label}: {key} {hm(et_)} exit {want} routed with the research $ ({pnl_want:+,.2f})", okX,
                  (x and {k: x.get(k) for k in ("t", "reason", "pnl", "pnl_est", "pnl_model")}, u))
            if want == "BE":
                be = tick_px(float(u["entry"]) + d * 1.25, d)
                check(f"{label}: {key} {hm(et_)} breakeven move routed (stop -> {be:,.2f})",
                      any(abs(float(m["stop"]) - be) < 1e-6 and (m.get("result") or {}).get("ok") for m in mods.get(et_, [])), mods.get(et_))
        rows.append({"entry": hm(et_), "routed": bool(e), "delay_s": delay, "qty": e and e.get("qty"), "exit": x and x.get("reason"),
                     "pnl": x and x.get("pnl")})
    bad = one_position(b)
    n_ent = collections.Counter(live.trading_day(int(r["entry_t"])) for r in led if r.get("side") in ("buy", "sell"))
    check(f"{label}: one position at a time (ledger + fake NinjaTrader), <= 2 entries a day", not bad and mx <= 1 and max(n_ent.values() or [0]) <= 2,
          (bad, mx, n_ent))
    recon = [r for r in led if r.get("reason") == "RECONCILE"]
    check(f"{label}: no error, no RECONCILE flatten, no DESYNC", not errors and not recon and not b.health.get("desync"),
          (errors[:3], recon[:2], [x["text"] for x in b.log if "DESYNC" in x["text"]][:2]))
    return {"day": day, "key": key, "rows": rows, "lit": len(L), "seconds": round(time.time() - t0), "bot": b}


# ------------------------------------------------------------------------------------------------ unit checks
def units():
    print("unit checks: sizing, guards, switch", flush=True)
    # sizing: research eval-safe size (tools/second_ema.ema_eval_qty, base usd500)
    from tools import second_ema as SE
    st = {"profit": 400.0, "cum": -300.0, "room": 900.0, "session": 3, "n_today": 0, "days_traded": 2}
    cfg = {"mode": "two_week"}
    ok = True
    for rp in (8.0, 15.0, 25.0, 40.0, 79.0):
        a = SZ.second_qty(rp, 500.0, cfg, state=dict(st))["qty"]
        b = SE.ema_eval_qty({"risk_pts": rp}, st, base="usd500")
        ok &= a == b
    check("sizing: engine/sizing.second_qty == the research eval-safe size (ema_eval_qty usd500) on 5 stops", ok)
    check("sizing: normal mode = $500 / (stop x $2), 1-40", SZ.second_qty(20.0, 500.0, {"mode": "normal"})["qty"] == 12
          and SZ.second_qty(3.0, 500.0, {})["qty"] == 40 and SZ.second_qty(300.0, 500.0, {})["qty"] == 1)
    check("sizing: a failed eval (room <= 0) -> 0", SZ.second_qty(20.0, 500.0, cfg, state={**st, "room": -5.0})["qty"] == 0)
    check("sizing: a passed eval (pass lock) -> 0", SZ.second_qty(20.0, 500.0, cfg, state={**st, "profit": 3100.0, "cum": 0.0})["qty"] == 0)
    check("sizing: eval mode with the room unknown -> 0 (fails closed)", SZ.second_qty(20.0, 500.0, cfg, state=None, room=None)["qty"] == 0)
    check("sizing: the $1,000 soft daily loss is shared (today -$900 -> at most 2 micros at a 20-pt stop)",
          SZ.second_qty(20.0, 500.0, cfg, state={**st, "cum": -900.0, "room": 5000.0})["qty"] == 2)
    # the bot's own eval state feeds it (two_week: the eval's earlier days + today's routed LIT exit, shared with LIT)
    lb = live.LiveBot()
    now = at("2026-10-07", 5, 0)
    lb.clock = lambda: now
    lb.cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "eval_start": "2026-10-05"}
    lb._lit_sizing = {"mode": "two_week"}
    lb._eval_prev = {"2026-10-05": 650.0, "2026-10-06": -420.0}
    lb.ledger = [{"t": now - 3600, "side": "exit", "pnl": -380.0, "entry_t": now - 5400}]
    est = lb.eval_state()
    for rp in (12.0, 33.5, 70.0):
        q_bot = lb._second_qty({"usd": 500}, {"risk_pts": rp})[0]
        q_res = SE.ema_eval_qty({"risk_pts": rp}, {"room": est["room"], "cum": est["cum"]}, base="usd500")
        ok &= q_bot == q_res
    check(f"sizing: LiveBot._second_qty uses LIT's eval state (room ${est['room']:,.0f}, today ${est['cum']:+,.0f}) = research size",
          ok and est["cum"] == -380.0, est)
    # guards: max 2 a day, 1 second strategy, LIT's own 1
    from engine import guards
    from engine import lit as L

    class B:
        pass
    b = B()
    day = "2026-10-01"
    t0 = at(day, 3, 0)
    b.ledger = []
    b.cfg = {"guards": {}}
    b.state = {"strategy": {"model": "lit", "params": {**L.DEFAULTS, "max_per_day": 1}}}
    b._second_routed = ["ema_lon_vix"]
    c = guards.config(b)
    check("guards: max_per_day 2 when a routed second strategy is on (1 otherwise)", c["max_per_day"] == 2 and
          guards.config(type("X", (), {"cfg": {}, "_second_routed": []})())["max_per_day"] == 1)
    s = {}
    b.ledger = [{"side": "buy", "entry_t": t0, "src": "ema_lon_vix"}]
    p_sec = guards.dup_problem(b, t0 + 3600, c, s, src="macd_sweep")
    p_lit = guards.dup_problem(b, t0 + 3600, c, s, src=None)
    check("guards: after 1 second-strategy entry: another second strategy blocked, LIT allowed", p_sec and p_lit is None, (p_sec, p_lit))
    b.ledger.append({"side": "sell", "entry_t": t0 + 1800})
    p3 = guards.dup_problem(b, t0 + 7200, c, s, src=None)
    check("guards: after LIT + 1 second: a 3rd entry blocked (2 a day)", bool(p3), p3)
    b.ledger = [{"side": "sell", "entry_t": t0}]
    check("guards: after LIT's trade: LIT's own 2nd blocked (LIT max 1), a second strategy allowed",
          guards.dup_problem(b, t0 + 3600, c, s, src=None) and guards.dup_problem(b, t0 + 3600, c, s, src="ema_lon_vix") is None)
    # the switch
    tmp = tempfile.mkdtemp(prefix="le_second_sw_")
    try:
        p = os.path.join(tmp, "second_model.json")
        shutil.copy(second.CFG_PATH, p)
        raw = open(p, encoding="utf-8").read()
        r1 = second.set_route("ema_lon_vix", True, path=p, selftest=lambda: (False, "FAIL (1/69)"))
        same = open(p, encoding="utf-8").read() == raw
        r2 = second.set_route("ema_lon_vix", True, path=p, selftest=lambda: (True, "PASS"))
        c2 = json.load(open(p, encoding="utf-8"))
        r3 = second.set_route("lit_asia", True, path=p, selftest=lambda: (True, "PASS"))
        r4 = second.set_route("ema_lon_vix", False, path=p)
        back = open(p, encoding="utf-8").read() == raw
        check("switch: refused when engine.ninjatrader --selftest fails (file untouched)", not r1["ok"] and same, r1)
        check("switch: --route ema_lon_vix on edits that one flag; off restores the file byte for byte",
              r2["ok"] and c2["strategies"]["ema_lon_vix"]["route"] is True and not c2["strategies"]["macd_sweep"]["route"] and r4["ok"] and back,
              (r2, r4))
        check("switch: a cloud-only strategy can never be routed", not r3["ok"], r3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    shipped = json.load(open(second.CFG_PATH, encoding="utf-8"))
    check("second_model.json ships with \"route\": false for every strategy (nothing switched on)",
          all(not s_.get("route") for s_ in shipped["strategies"].values()) and second.routed() == [],
          {k: v.get("route") for k, v in shipped["strategies"].items()})
    src = open(os.path.join(ROOT, "engine", "second.py"), encoding="utf-8").read()
    check("engine/second.py imports no adapter (routing lives in engine/live.py)",
          "import ninjatrader" not in src and "from .ninjatrader" not in src and "from engine.ninjatrader" not in src
          and "from .live" not in src and "tradovate" not in src.lower().replace("tradovate adapter", ""))


# ------------------------------------------------------------------------------------------------ a. route off
def part_a(H, quick=False):
    print("a. route off = today", flush=True)
    if not quick:
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", "tests.test_lit_live", "--days", "--bot"], cwd=ROOT, capture_output=True,
                           text=True, timeout=1800)
        out = p.stdout or ""
        lines = [x for x in out.splitlines() if "day-end" in x.lower() or "LiveBot" in x or x.strip() in ("OK",)]
        check("tests.test_lit_live --days --bot passes (120/120 day-end, LiveBot entries 2/2 exits 2/2)", p.returncode == 0,
              out[-1500:])
        print("     " + "\n     ".join(lines[-4:]), flush=True)
    day = "2026-10-01"
    b, fake = H.bot("off_" + day, [], at(day, 1, 45))
    errors = []
    H.run(b, fake, H.times(day, ["ema_lon_vix"]), errors)
    srcs = [r for r in b.ledger if r.get("src")]
    lit = [r for r in b.ledger if r.get("side") in ("buy", "sell")]
    check(f"a. {day} route off: LIT routed ({len(lit)}), 0 second-strategy routes (the EMA trade of that day stays paper)",
          not srcs and len(lit) == len(H.ref.lit.get(day, [])) and not errors, (srcs[:2], errors[:2]))


# ------------------------------------------------------------------------------------------------ d. exception
def part_d(H):
    print("d. a failing second strategy never blocks or delays LIT", flush=True)
    day = "2026-10-01"
    real = second.run
    second.run = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected second-strategy failure"))
    try:
        b, fake = H.bot("exc_" + day, ["ema_lon_vix"], at(day, 1, 45))
        errors = []
        H.run(b, fake, H.times(day, ["ema_lon_vix"]), errors)
    finally:
        second.run = real
    b2, fake2 = H.bot("exc_ref_" + day, [], at(day, 1, 45))
    H.run(b2, fake2, H.times(day, ["ema_lon_vix"]), [])
    e1 = [(r["entry_t"], r["side"], r["qty"], r["stop"], r["target"]) for r in b.ledger if r.get("side") in ("buy", "sell")]
    e2 = [(r["entry_t"], r["side"], r["qty"], r["stop"], r["target"]) for r in b2.ledger if r.get("side") in ("buy", "sell")]
    d1 = [round(r["t"] - r["entry_t"], 1) for r in b.ledger if r.get("side") in ("buy", "sell")]
    d2 = [round(r["t"] - r["entry_t"], 1) for r in b2.ledger if r.get("side") in ("buy", "sell")]
    x1 = [(r["entry_t"], r["reason"], r.get("pnl")) for r in b.ledger if r.get("side") == "exit"]
    x2 = [(r["entry_t"], r["reason"], r.get("pnl")) for r in b2.ledger if r.get("side") == "exit"]
    err = [x["text"] for x in b.log if "second-strategy route failed" in x["text"] or "injected" in x["text"]]
    check(f"d. {day}: second-strategy code raising every poll -> LIT's entries / exits identical to route off ({len(e1)} entries, "
          f"delay {d1} s vs {d2} s), the error logged, no poll failed", e1 == e2 and x1 == x2 and not errors and bool(err)
          and all(abs(a - b_) <= 3.0 for a, b_ in zip(d1, d2)), (e1, e2, x1, x2, errors[:2], err[:1]))


# ------------------------------------------------------------------------------------------------ e. restart
def part_e(H):
    print("e. restart mid-trade", flush=True)
    day = "2026-10-01"
    u = H.ref.sec["ema_lon_vix"][day][0]
    wakes = H.times(day, ["ema_lon_vix"])
    cut = int(u["entry_t"]) + 20 * 60
    b, fake = H.bot("rs_" + day, ["ema_lon_vix"], at(day, 1, 45))
    errors = []
    H.run(b, fake, [w for w in wakes if w < cut], errors)
    open1 = (b._open_routed, b._open_src)
    b.stop()
    nt_state = b.adapter.state_path if hasattr(b.adapter, "state_path") else None
    b2, _ = H.bot("rs_" + day, ["ema_lon_vix"], cut, fake=fake)
    restored = (b2._open_routed, b2._open_src)
    H.run(b2, fake, [w for w in wakes if w >= cut], errors)
    x = [r for r in b2.ledger if r.get("side") == "exit" and r.get("entry_t") == int(u["entry_t"])]
    recon = [r for r in b2.ledger if r.get("reason") == "RECONCILE"]
    check(f"e. {day}: restart at {hm(cut)} with the EMA trade open -> recognised ({restored[1]} @ {hm(restored[0]) if restored[0] else None})",
          open1 == restored and restored[1] == "ema_lon_vix", (open1, restored, nt_state))
    check(f"e. after the restart the EMA trade is managed to its exit ({kind_reason(u['exit_kind'])}) and never reconciled as "
          "a manual trade", len(x) == 1 and x[0]["reason"] == kind_reason(u["exit_kind"]) and not recon and not errors
          and b2._open_routed is None, (x, recon[:2], errors[:2]))


def run_suites():
    print("f. other suites", flush=True)
    for mod, args in (("engine.ninjatrader", ["--selftest"]), ("tests.test_guards", []), ("tests.test_eval_lifecycle", []),
                      ("tests.test_second", ["--quick"]), ("tests.test_pcdash_api", []), ("tests.test_alerts_plus", []),
                      ("tests.test_no_yahoo", [])):
        t0 = time.time()
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", mod] + args, cwd=ROOT, capture_output=True, text=True, timeout=3600)
        tail = [x for x in (p.stdout or "").splitlines() if x.strip()][-1:] or [(p.stderr or "")[-200:]]
        check(f"f. {mod} {' '.join(args)} ({round(time.time() - t0)} s): {tail[0][:120]}", p.returncode == 0, (p.stdout or "")[-1500:] + (p.stderr or "")[-800:])


def main():
    quick = "--quick" in sys.argv
    t_all = time.time()
    ref = Ref()
    units()
    H = Harness(ref)
    out = {"days": []}
    try:
        part_a(H, quick)
        print("b. route on: ema_lon_vix", flush=True)
        ema_days = ["2026-10-01"] if quick else ["2026-10-01", "2026-10-06", "2026-09-18", "2026-09-15", "2026-09-04", "2026-09-10", "2026-09-22"]
        only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--ema-days=")), None)
        ema_days = only or ema_days
        for d in ema_days:
            r = day_check(H, "ema_lon_vix", d, f"b. {d}")
            out["days"].append({k: v for k, v in r.items() if k != "bot"})
            print(f"     {d}: {r['rows']} ({r['seconds']} s)", flush=True)
        if not quick:
            print("c. macd_sweep / sr_nyreclaim", flush=True)
            for k, d in (("macd_sweep", "2026-07-10"), ("macd_sweep", "2026-09-28"), ("sr_nyreclaim", "2026-09-16")):
                r = day_check(H, k, d, f"c. {d}")
                out["days"].append({kk: v for kk, v in r.items() if kk != "bot"})
                print(f"     {k} {d}: {r['rows']} ({r['seconds']} s)", flush=True)
        part_d(H)
        if not quick:
            part_e(H)
    finally:
        H.close()
    if "--suites" in sys.argv:
        run_suites()
    n_ok = sum(1 for _, ok in RESULTS if ok)
    out.update(results=[{"name": n, "ok": ok} for n, ok in RESULTS], passed=n_ok, total=len(RESULTS), seconds=round(time.time() - t_all))
    if not quick:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)
    print(f"second-strategy route: {n_ok}/{len(RESULTS)} checks passed in {out['seconds']} s")
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
