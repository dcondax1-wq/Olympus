"""Full-day rehearsal of the PC's exact live set-up (night-rehearse 2026-11-18). PAPER: simulated NinjaTrader only.

The owner's PC runs ZEUS live on three MFFU accounts at once (new this week, never rehearsed together):
  Zlarior (LIT) on the Builder 50K eval          the bot's own account (data/start_bot.json "lit")
  Zlarior (LIT) on a new Builder 25K eval        an extra account, id b25k_2 (engine/account_cli.py -> data/accounts.json)
  ATLAS on the FUNDED Builder 25K                account B, funded stage (engine/lit25.py --funded -> data/account_b.json)
  (+ the Rapid EOD 25K soon: LIT + ATLAS lanes on one account, engine/rapid.py -> data/rapid.json; --rapid adds it)

This tool rebuilds that config in a temp folder the way ADD_ACCOUNT.bat writes it (the same functions: engine.go,
engine.account_b.set_account_b, engine.lit25.to_funded, engine.account_cli.add / arm, engine.rapid.arm, go.arm_b), builds the
start body exactly as `engine.ninjatrader --start` does (multi_account.merge_into_start + the typed phrase), starts the REAL
LiveBot (engine/live.py) with every account's NinjaTrader adapter on ONE simulated NinjaTrader (engine.ninjatrader._FakeNT,
the tests' fake; its price walks each 1m bar o -> h/l -> c), and replays real days (data/NQ_1m.csv + NQ_5m.csv, TradingView
CME futures) minute by minute, like the PC's 60 s poll.

Days (2026; the data ends 10-16, so the Thanksgiving-like halt is Labor Day, the same 13:00 ET CME halt):
  09-07  early close: CME halts 13:00 ET; LIT's short is held to the halt in the backtest -> the bot must be flat at 12:55
  10-02  news: jobs report 08:30 (LIT + ATLAS both long through it)
  10-06  opposite sides: ATLAS long 04:10 on the funded 25K, LIT goes short at 04:32 (MFFU hedging rule)
  10-07  LIT long held into the close: flat by 15:55 on every account
  10-13  LIT's big winner (the 50K can pass; lifecycle + payout numbers)
Each account's money is today's (2026-11-17: 50K $49,192.78 / floor $48,168.20; the 25K #2 fresh; the funded 25K fresh),
placed on the day before each replayed day (the market days are old, the books are the PC's).

Checks per day: each account's size for its plan, never opposite positions across accounts, the 25K #2 eval and the funded
25K never confused (names, order tags, state files, books), flat by 16:10 (15:55) and 5 min before an early close, lifecycle
stages, payout coach numbers for the funded 25K, board events, the ntfy status payload < 3,900 bytes, restart mid-trade
(a new LiveBot on the same files picks the open trades up, no double order) and kill / flatten reaching every account.

    python -X utf8 tools/rehearse_day.py                 # the 3 live accounts, every day (~minutes)
    python -X utf8 tools/rehearse_day.py --rapid         # + the Rapid EOD 25K (LIT + ATLAS lanes)
    python -X utf8 tools/rehearse_day.py --days 2026-10-06 --scenarios none --quick   # one day, fewer polls (5-min + key windows)
    (default: every minute 01:50-16:20 ET, every 5 min in the evening before; --full: every minute from 18:00)
Writes research/lab/rehearse_day.json (the findings). Temp files only; no real NinjaTrader folder is ever touched (every
adapter is forced onto the temp folder and checked), NINJATRADER_LIVE=1 exists only inside this process, against the fake.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "lab", "rehearse_day.json")
# made-up MFFU-style Names (never the owner's): EV = eval, SF = sim funded (engine/onboard.py)
N50 = "MFFUEVBLDR50K-RH01"           # Zlarior's Builder 50K eval (the bot's own account)
N25 = "MFFUEVBLDR25K-RH02"           # Zlarior's new Builder 25K eval (b25k_2)
NB_EVAL = "MFFUEVBLDR25K-RH03"       # ATLAS's passed 25K eval (MFFU locked it)
NBF = "MFFUSFBLDR25K-RH03"           # ATLAS's FUNDED Builder 25K (account B)
NR = "MFFUEVRPDEOD25K-RH04"          # the Rapid EOD 25K (--rapid)
NR2 = "MFFUEVRPDEOD50K-RH05"         # the Rapid EOD 50K as Rapid #2 (--rapid2, data/rapid2.json: day-multirapid 2026-11-20)
BAL50, FLOOR50 = 49192.78, 48168.20  # Zlarior 50K on 2026-11-17 (STATE.md)
DAYS = [("2026-09-07", "early close (Labor Day: CME halts 13:00 ET, like Thanksgiving)"),
        ("2026-10-02", "news day (jobs report 08:30)"),
        ("2026-10-06", "opposite sides (ATLAS long 04:10, LIT short 04:32)"),
        ("2026-10-07", "LIT long held into the close"),
        ("2026-10-13", "LIT's big winner")]
MAX_STATUS_BYTES = 3900
FLAT_LAST = 16 * 60 + 10             # MFFU: flat by 16:10 ET
RAPID_BEST_DAY = 0.3 * 1500.0        # MFFU Rapid EOD 25K eval: best day <= 30% of the profit (= $450 at the $1,500 target)
RAPID2_BEST_DAY = 0.3 * 3000.0       # the Rapid EOD 50K: 30% of the $3,000 target


def ts(day: str, hh: int, mm: int = 0, ss: int = 0) -> int:
    d = dt.date.fromisoformat(day)
    if hh >= 18:
        d -= dt.timedelta(days=1)
    return int(dt.datetime.combine(d, dt.time(hh, mm, ss), ET).timestamp())


def hm(t) -> str:
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M:%S")


def prev_weekday(day: str) -> str:
    d = dt.date.fromisoformat(day) - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.isoformat()


# extra runs of the opposite-sides day (what can go wrong on it): {name: run_day kwargs}
SCENARIOS = {
    "slow-close": ("2026-10-06", "opposite sides + NinjaTrader picks the funded 25K's orders up 4 min late",
                   {"hold": {NBF: (ts("2026-10-06", 4, 33), ts("2026-10-06", 4, 37))}}),
    "passed50": ("2026-10-06", "opposite sides with Zlarior's 50K already PASSED (stood down)", {"passed50": True}),
    "kill": ("2026-10-07", "KILL at 11:00 with LIT long on both evals and ATLAS long on the funded 25K",
             {"kill_at": ts("2026-10-07", 11, 0, 3)}),
    "flatten": ("2026-10-13", "phone FLATTEN at 07:30 with LIT short on both evals", {"flatten_at": ts("2026-10-13", 7, 30, 3)}),
}
RESTART = {"2026-10-02": ts("2026-10-02", 5, 0, 3), "2026-10-13": ts("2026-10-13", 7, 0, 3)}   # STOP + START mid-trade

# ================================================================================================ findings
class Findings:
    def __init__(self):
        self.checks, self.found = [], []

    def check(self, name, ok, detail="", sev="high"):
        self.checks.append({"name": name, "ok": bool(ok), "detail": None if ok else str(detail)[:900], "sev": sev})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:500]}"), flush=True)
        return bool(ok)

    def note(self, sev, text):
        self.found.append({"sev": sev, "text": text})
        print(f"  [{sev.upper()}] {text}", flush=True)


# ================================================================================================ the rig
class Rig:
    """One temp PC: its config files, one simulated NinjaTrader, a replay clock and the bar source."""

    def __init__(self, tmp, frames, rapid=False, rapid2=False):
        from engine.ninjatrader import _FakeNT
        self.tmp, self.frames, self.rapid, self.rapid2 = tmp, frames, rapid or rapid2, rapid2
        self.data = os.path.join(tmp, "data")
        os.makedirs(self.data, exist_ok=True)
        self.folder = os.path.join(tmp, "NinjaTrader 8")
        self.fake = _FakeNT(self.folder, price=25000.0)
        import threading
        self.mx = threading.RLock()              # the accounts route in parallel threads: one NinjaTrader at a time
        self.hold = {}                           # NinjaTrader account -> unix time: its order files wait in incoming\ until then

        def process(*_a):
            """_FakeNT.process, one thread at a time, leaving a held account's files where they are (a slow NinjaTrader)."""
            fk = self.fake
            with self.mx:
                for name in sorted(os.listdir(fk.inc)):
                    path = os.path.join(fk.inc, name)
                    try:
                        with open(path, "rb") as fh:
                            raw = fh.read()
                    except FileNotFoundError:
                        continue
                    lines = raw.decode("ascii", "replace").splitlines()
                    if any(self.now < until and f";{acct};" in ln for acct, until in self.hold.items() for ln in lines):
                        continue
                    os.remove(path)
                    if not (name.lower().startswith("oif") and name.lower().endswith(".txt")):
                        fk.errors.append((name, "Unknown OIF file type"))
                        continue
                    fk.files.append((name, lines))
                    for ln in lines:
                        fk._do(ln)
        self.fake.process = process
        self.fill_hedges = []                    # every fill that left one account long and another short (any instant)
        self.fills = []
        raw_fill = self.fake._fill

        def _fill(oid, qty, px, raw_fill=raw_fill):
            raw_fill(oid, qty, px)
            o = self.fake.orders.get(oid) or {}
            pos = positions(self)
            self.fills.append((self.now, o.get("account"), o.get("action"), qty, px, dict(pos)))
            if any(q > 0 for q in pos.values()) and any(q < 0 for q in pos.values()):
                self.fill_hedges.append((hm(self.now), o.get("account"), o.get("action"), qty, dict(pos)))
        self.fake._fill = _fill
        self.now = 0
        self.adapters = []                       # every NinjaTraderAdapter made (checked: all on the temp folder)
        self.alerts = []
        o1 = frames[("NQ", "1m")]
        self.o1 = dict(zip(o1["time"].astype("int64"), o1["open"].astype(float)))
        self.bars1 = {int(r.time): (float(r.open), float(r.high), float(r.low), float(r.close)) for r in o1.itertuples()}

    # ---- clock + bars (tests/test_live_dryrun.Replay: only closed bars are visible)
    def clock(self):
        return self.now

    def read_hist(self, sym, tf):
        from engine.data import TF_SECONDS
        df = self.frames.get((sym, tf))
        if df is None:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        return df[df["time"] + TF_SECONDS[tf] <= self.now]

    def fetch_recent(self, sym, interval, period="5d"):
        t = self.now - self.now % 60                 # the forming 1m bar's first tick (a live feed shows it)
        if sym == "NQ" and interval == "1m" and t in self.o1:
            o = self.o1[t]
            return pd.DataFrame([{"time": t, "open": o, "high": o, "low": o, "close": o, "volume": 0.0}])
        return pd.DataFrame()

    # ---- the simulated NinjaTrader
    def walk(self, t_bar):
        """The 1m bar opening at t_bar trades through the fake: o, then the nearer extreme, the other, c."""
        b = self.bars1.get(int(t_bar))
        if not b:
            return
        o, h, l, c = b
        path = (o, l, h, c) if (o - l) < (h - o) else (o, h, l, c)
        for px in path:
            self.fake.move(px)
            self.fake.process()

    def adapter(self, cfg):
        from engine.ninjatrader import NinjaTraderAdapter
        c = {**cfg, "nt_folder": self.folder, "nt_allow_path": os.path.join(self.data, "nt_accounts_allow.json")}
        # the bot's own account has no state / audit path in its start cfg (the PC uses data/ninjatrader_state.json and
        # logs/): here always the temp PC's, never this repo's (a rehearsal on the PC must not touch the live bot's files)
        tag = str(c.get("nt_file_tag") or "")
        for k, fn in (("nt_state_path", f"ninjatrader_state{('_' + tag.strip('_')) if tag else ''}.json"),
                      ("nt_audit_log", f"ninjatrader_oif{('_' + tag.strip('_')) if tag else ''}.log")):
            if not str(c.get(k) or "").startswith(self.tmp):
                c[k] = os.path.join(self.data, fn)
        ad = NinjaTraderAdapter(c, clock=self.clock)
        if not (str(ad.state_path).startswith(self.tmp)):
            raise RuntimeError(f"adapter state file {ad.state_path} is not in the temp PC: refused")
        if os.path.abspath(ad.folder) != os.path.abspath(self.folder):
            raise RuntimeError(f"adapter folder {ad.folder} is not the simulated one: refused")

        def _sleep(s, ad=ad):
            self.fake.process()
            self.now += s
        ad._sleep = _sleep
        ad._alert_fn = lambda *a, **k: self.alerts.append((self.now, a[0] if a else ""))
        self.adapters.append(ad)
        return ad

    def install(self):
        """Every adapter factory -> the simulated NinjaTrader; alerts / news / push off; board + lifecycle in temp."""
        from engine import account_b as AB, alerts, fleet, gamma, live, multi_account as MA, news
        self._saved = {"MA": MA.ADAPTER_FACTORY, "AB": AB.ADAPTER_FACTORY, "FL": fleet.ADAPTER_FACTORY,
                       "NT": live.ADAPTERS["ninjatrader"], "alerts": alerts.send, "ff": news.ff_calendar,
                       "vol": news.volatility, "guard": news.guard, "gamma": gamma.refresh_history}
        MA.ADAPTER_FACTORY = lambda acc, cfg: self.adapter(cfg) if cfg.get("adapter") == "ninjatrader" else live.PaperAdapter(cfg)
        AB.ADAPTER_FACTORY = lambda spec, cfg: self.adapter(cfg) if cfg.get("adapter") == "ninjatrader" else live.PaperAdapter(cfg)
        fleet.ADAPTER_FACTORY = MA.ADAPTER_FACTORY
        live.ADAPTERS["ninjatrader"] = self.adapter
        alerts.send = lambda text, kind="signal", force=False: (self.alerts.append((self.now, text)), {"sent": True})[1]
        news.ff_calendar = lambda: []
        news.volatility = lambda: {}
        news.guard = lambda now=None, params=None, vol=None, events=None: {"allowed": True, "reasons": [], "regime": None,
                                                                          "next_high": None, "now": now}
        gamma.refresh_history = lambda max_age_h=12: os.path.join(ROOT, "data", "GEX_1d.csv")
        from engine import memory
        self._saved["memory"] = memory.MEMORY
        memory.MEMORY = memory.Memory(os.path.join(self.data, "memory.db"))     # the trade memory: the temp PC's, not data/

    def uninstall(self):
        from engine import account_b as AB, alerts, fleet, gamma, live, multi_account as MA, news
        s = getattr(self, "_saved", None)
        if not s:
            return
        MA.ADAPTER_FACTORY, AB.ADAPTER_FACTORY, fleet.ADAPTER_FACTORY = s["MA"], s["AB"], s["FL"]
        live.ADAPTERS["ninjatrader"] = s["NT"]
        alerts.send, news.ff_calendar, news.volatility, news.guard = s["alerts"], s["ff"], s["vol"], s["guard"]
        gamma.refresh_history = s["gamma"]
        from engine import memory
        memory.MEMORY = s["memory"]


# ================================================================================================ the PC's config (ADD_ACCOUNT.bat)
@contextlib.contextmanager
def pc_paths(rig):
    """engine.go / account_b / lit25 / rapid / multi_account pointed at the temp PC's files."""
    from engine import account_b as AB, go, lit25, multi_account as MA, rapid, second
    saved = (go.CFG, go.SECOND_PATH, go.ALLOW_PATH, go.ACCOUNTS_PATH, go.ANCHOR_PATH, go.bot_running, go.nt_balances,
             lit25.PATH, rapid.PATH, second._selftest_ok, second.CFG_PATH)
    sm = os.path.join(rig.tmp, "second_model.json")
    if not os.path.exists(sm):
        with open(os.path.join(ROOT, "second_model.json"), encoding="utf-8") as fh:
            c = json.load(fh)
        c["account_b"] = None                       # the tracked file ships null; the PC's block is data/account_b.json
        with open(sm, "w", encoding="utf-8") as fh:
            json.dump(c, fh, indent=1)
    go.CFG = os.path.join(rig.data, "start_bot.json")
    go.SECOND_PATH = sm
    go.ALLOW_PATH = os.path.join(rig.data, "nt_accounts_allow.json")
    go.ACCOUNTS_PATH = os.path.join(rig.data, "accounts.json")
    go.ANCHOR_PATH = os.path.join(rig.data, "eval_anchor.json")
    go.bot_running = lambda: False
    go.nt_balances = lambda: {N50: BAL50, N25: 25000.0, NB_EVAL: 26946.10, NBF: 25000.0, NR: 25000.0, NR2: 50000.0}
    lit25.PATH = os.path.join(rig.data, "lit25.json")
    rapid.PATH = os.path.join(rig.data, "rapid.json")
    second._selftest_ok = lambda *a, **k: (True, "rehearsal: engine.ninjatrader --selftest is run on its own")
    second.CFG_PATH = sm
    try:
        yield sm
    finally:
        (go.CFG, go.SECOND_PATH, go.ALLOW_PATH, go.ACCOUNTS_PATH, go.ANCHOR_PATH, go.bot_running, go.nt_balances,
         lit25.PATH, rapid.PATH, second._selftest_ok, second.CFG_PATH) = saved


def build_pc(rig, day: str, F: Findings, quiet=True) -> dict:
    """Write the PC's files the way the owner's steps did, for a session `day`; return the start body + what was written."""
    from engine import account_b as AB, account_cli, go, lit25, multi_account as MA, rapid
    from engine.tradovate import LIVE_PHRASE
    out = io.StringIO()
    with pc_paths(rig) as sm, contextlib.redirect_stdout(out if quiet else sys.stdout):
        prev = prev_weekday(day)
        # 1. START BOT's first run: the two names (start_bot.json), launch prep put ATLAS on its 25K eval (account_b, local)
        go._save({"lit": N50, "atlas": NB_EVAL, "prepped": True, "setup_done": True})
        r = AB.set_account_b(NB_EVAL, plan="builder25k", start="2026-10-27", path=sm)
        go._allow(N50)
        go._allow(NB_EVAL)
        # Zlarior's real balance: the eval anchor (python -m engine.eval_life --anchor), on the day before the replayed day
        with open(go.ANCHOR_PATH, "w", encoding="utf-8") as fh:
            json.dump({"main": {"as_of": prev, "balance": BAL50, "floor": FLOOR50}}, fh)
        # 2. ADD_ACCOUNT.bat item 1: the new Builder 25K eval (Zlarior trades it) -> b25k_2, DISARMED
        a1 = account_cli.add("builder25k", N25, start=day)
        # 3. ADD_ACCOUNT.bat item 4: ATLAS's FUNDED 25K after MFFU's upgrade -> engine.lit25 --funded "<Name>" --start <day>
        a2 = lit25.to_funded(NBF, day)
        # 4. --rapid: ADD_ACCOUNT.bat item 5, the Rapid EOD 25K (LIT + ATLAS)
        a3 = account_cli.add("rapideod25", NR, start=day) if rig.rapid else None
        # 4b. --rapid2: the add box again, Rapid EOD 50K -> Rapid #2 (data/rapid2.json)
        a4 = account_cli.add("rapideod", NR2, start=day) if getattr(rig, "rapid2", False) else None
        # 5. START BOT + the typed phrase (engine/go.step_arm): ATLAS's 25K, the Rapid, the added accounts, then --start
        cfg = go._read(go.CFG)
        rb = go.arm_b(cfg["atlas"])
        rr = rapid.arm(LIVE_PHRASE)
        ra = account_cli.arm(LIVE_PHRASE)
        inv = account_cli.inventory()
        body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60,
                "data_source": "ninjatrader", "nt_account": cfg["lit"], "confirm": LIVE_PHRASE}
        body = MA.merge_into_start(body, LIVE_PHRASE, path=go.ACCOUNTS_PATH)
        # what the real bot reads by itself from data/ (a test bot needs them in its start cfg)
        body["account_b"] = AB.raw_cfg(sm)
        body["rapid"] = rapid.read()
        body["rapid2"] = rapid.read(rapid.slot_path("rapid2"))
        body["lit25"] = lit25.load()
        # live_model.json lit_sizing.eval_start is 2026-10-19 (session ~21 on 11-17): the same age on the replayed day
        body["eval_start"] = (dt.date.fromisoformat(day) - dt.timedelta(days=29)).isoformat()
        anchor = json.load(open(go.ANCHOR_PATH, encoding="utf-8"))["main"]
        body["eval_anchor"] = anchor
        files = {n: json.load(open(p, encoding="utf-8")) for n, p in
                 (("start_bot.json", go.CFG), ("accounts.json", go.ACCOUNTS_PATH), ("account_b.json", AB.local_path(sm)),
                  ("nt_accounts_allow.json", go.ALLOW_PATH)) if os.path.exists(p)}
        if os.path.exists(rapid.path()):
            files["rapid.json"] = json.load(open(rapid.path(), encoding="utf-8"))
        files["lit25.json"] = lit25.load() or "(missing = OFF)"
    say = out.getvalue()
    steps = {"atlas_eval": r, "add_25k": a1, "funded": a2, "add_rapid": a3, "add_rapid2": a4, "arm_b": rb, "arm_rapid": rr,
             "arm_added": ra}
    bad = {k: v for k, v in steps.items() if isinstance(v, dict) and v.get("ok") is False and not (k == "arm_rapid" and not rig.rapid)}
    F.check(f"{day} config: ADD_ACCOUNT steps (25K eval add, lit25 --funded, " + ("Rapid 25K add, " if rig.rapid else "")
            + "START BOT arming) all OK", not bad, bad)
    return {"body": body, "files": files, "inventory": inv, "steps": steps, "say": say}



# ================================================================================================ plan checks
# what each account's plan allows one trade to lose at its full stop-out (stop + 2 ticks of slippage, $1.90 a micro: the
# research / dll_guard measure), relative to that account's room to its max-loss floor at the trade: (share of the room,
# $ cap, the soft daily loss, max micros). Builder evals: LIT two_week = 40% of the room (owner: "yes 40%", 25K = the same
# rule since 2026-11-17); funded 25K ATLAS: 60% of the room <= $750 (engine/account_b.funded_qty on the 25K funded preset);
# Rapid 25K: LIT two_week on $1,500 / $1,000 / 20 micros + soft $500 day, ATLAS min($250, 30% of the room).
PLAN_CAPS = {"Zlarior 50K (main)": (0.4, None, 1000.0, 40), "Zlarior 25K #2 (b25k_2)": (0.4, None, 600.0, 20),
             "ATLAS funded 25K (B)": (0.6, 750.0, 600.0, 20), "Rapid 25K LIT lane": (0.4, None, 500.0, 20),
             "Rapid 25K ATLAS lane": (0.3, 250.0, 500.0, 20),
             "Rapid 50K LIT lane": (0.4, None, 1000.0, 30), "Rapid 50K ATLAS lane": (0.3, 500.0, 1000.0, 30)}
BOOK = {"Zlarior 50K (main)": "50k", "Zlarior 25K #2 (b25k_2)": "25k2", "ATLAS funded 25K (B)": "f25",
        "Rapid 25K LIT lane": "rapid", "Rapid 25K ATLAS lane": "rapid", "Rapid 50K LIT lane": "rapid2", "Rapid 50K ATLAS lane": "rapid2"}
ROOM0 = {"50k": round(BAL50 - FLOOR50, 2), "25k2": 1000.0, "f25": 1000.0, "rapid": 1000.0, "rapid2": 2000.0}


def full_stop(qty, entry, stop) -> float:
    return float(qty) * ((abs(float(entry) - float(stop)) + 0.5) * 2.0 + 1.90)


def closes_of(bot) -> list:
    """[(book, exit_t, pnl, lane)] of every routed exit this day."""
    out = []
    for k, (o, _ad) in lanes(bot).items():
        for row in getattr(o, "ledger", None) or []:
            if row.get("side") == "exit" and (row.get("result") or {}).get("ok") is not False and row.get("pnl") is not None:
                out.append((BOOK[k], int(row.get("t") or 0), float(row["pnl"]), k))
    return out


def size_checks(bot, day, F):
    """Every entry each account routed vs its plan's caps (room at that moment = the start room + the book's closed $)."""
    cl = closes_of(bot)
    rows, bad = [], []
    for k, (o, _ad) in lanes(bot).items():
        prov = getattr(o, "prov", None) or {}
        for row in getattr(o, "ledger", None) or []:
            if row.get("side") not in ("buy", "sell") or (row.get("result") or {}).get("ok") is False:
                continue
            pv = prov.get(int(row.get("entry_t") or 0)) or {}
            entry = row.get("entry") if row.get("entry") is not None else pv.get("entry")
            if entry is None or row.get("stop") is None:
                bad.append((k, hm(row["t"]), "no entry / stop in the ledger row"))
                continue
            b = BOOK[k]
            room = ROOM0[b] + sum(p for bk, t, p, _l in cl if bk == b and t < int(row["t"]))
            cum = sum(p for bk, t, p, _l in cl if bk == b and t < int(row["t"]))
            share, usd, dll, mx = PLAN_CAPS[k]
            risk = full_stop(row["qty"], entry, row["stop"])
            cap = min(x for x in (share * room, usd, dll + min(0.0, cum)) if x is not None)
            rows.append({"acct": k, "t": hm(row["t"]), "side": row["side"], "qty": row["qty"], "risk_usd": round(risk, 2),
                         "cap_usd": round(cap, 2), "room": round(room, 2)})
            # 5% + one micro of slack: the bots size on their own slippage model, never more than one micro over the share
            one = full_stop(1, entry, row["stop"])
            if int(row["qty"]) > mx or risk > cap * 1.05 + one * 0.999 and int(row["qty"]) > 1:
                bad.append(rows[-1])
    for r in rows:
        print(f"    size {r['acct']:26s} {r['t']} {r['side']:4s} {r['qty']:>2} micros: full stop ${r['risk_usd']:,.0f} vs plan cap "
              f"${r['cap_usd']:,.0f} (room ${r['room']:,.0f})")
    F.check(f"{day} every entry sized inside its own plan (room share, $ cap, soft daily loss, max micros): {len(rows)} entries",
            not bad, bad)
    return rows


def ntfy_bytes(bot, now) -> tuple:
    """The PC's 5-min ntfy status (tools/pc_report.lite + public) built from this bot's heartbeat payload: (bytes, trimmed)."""
    from engine import heartbeat as HB, live_publish
    from tools import pc_report
    hb = HB.Heartbeat(bot, push_fn=lambda *a, **k: {"ok": True}, notify_fn=lambda *a, **k: None, clock=lambda: now).payload()
    hb["t"] = int(now)
    snap = {"t": int(now), "hb": hb, "hb_t": int(now), "hb_age": 0, "hb_src": "local", "server": True, "nt": True,
            "market_open": True, "entry_hours": True, "mode": "live",
            "live": live_publish.build(hb, now=int(now), hb_last={"at": int(now), "ok": True}, every_s=300)}
    out = pc_report.public(pc_report.lite(snap))
    raw = json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return len(raw), out.get("trimmed"), out

# ================================================================================================ the bot
def make_bot(rig, body, state_path):
    from engine.live import LiveBot
    b = LiveBot()
    b.clock, b.read_hist, b.fetch_recent, b.state_path = rig.clock, rig.read_hist, rig.fetch_recent, state_path
    r = b.start(dict(body), spawn=False)
    return b, r


def lanes(bot) -> dict:
    """{label: (object, adapter)} of every account the bot routes."""
    out = {"Zlarior 50K (main)": (bot, bot.adapter)}
    for a in (getattr(bot.accts, "accounts", None) or []):
        lbl = {"b25k_2": "Zlarior 25K #2 (b25k_2)", "rapid": "Rapid 25K LIT lane", "rapid2": "Rapid 50K LIT lane",
               "lit25": "LIT on funded 25K"}.get(a.id, a.id)
        out[lbl] = (a, a.adapter)
    if bot.acct_b is not None:
        out["ATLAS funded 25K (B)"] = (bot.acct_b, bot.acct_b.adapter)
    if getattr(bot, "acct_r", None) is not None:
        out["Rapid 25K ATLAS lane"] = (bot.acct_r, bot.acct_r.adapter)
    if getattr(bot, "acct_r2", None) is not None:
        out["Rapid 50K ATLAS lane"] = (bot.acct_r2, bot.acct_r2.adapter)
    return out


def rapid_both_open(bot, slot="rapid"):
    """The Rapid's two lanes both holding / sending at this poll (a position, an entry or a close not confirmed yet at
    NinjaTrader, or the model's open trade): {lane: what} when BOTH are, else None. slot "rapid2" = the 2nd Rapid."""
    from engine.rapid import _open_leg, slot_of
    lit_l = next((a for a in (getattr(bot.accts, "accounts", None) or []) if a.spec.get("lane") == "rapid"
                  and slot_of(a.spec) == slot), None)
    ar = getattr(bot, "acct_r2" if slot == "rapid2" else "acct_r", None)
    if lit_l is None or ar is None:
        return None
    busy = {}
    for k, o in (("LIT lane", lit_l), ("ATLAS lane", ar)):
        lg = _open_leg(getattr(o, "adapter", None))
        if o.open_t is not None or lg:
            busy[k] = {"open_t": o.open_t, "leg": (lg or {}).get("status")}
    return busy if len(busy) == 2 else None


def positions(rig) -> dict:
    """NinjaTrader (the fake) positions: {account: signed qty}."""
    out = {}
    for (acct, _inst), (q, _avg) in rig.fake.pos.items():
        if q:
            out[acct] = out.get(acct, 0) + q
    return out


def working(rig) -> list:
    return [o for o in rig.fake.orders.values() if o.get("state") in ("WORKING", "ACCEPTED")]


def poll_times(day: str, quick: bool, want: list, full: bool = False) -> list:
    """The PC polls every 60 s (+3 s after the minute). Default: every minute from 01:50 ET (LIT / ATLAS trade from 02:00) to
    16:20, every 5 min in the quiet evening before; full: every minute from 18:00; quick: every 5 min, every minute only
    around the open, the early close and the flat time (and `want` windows)."""
    start, end = ts(day, 18, 0), ts(day, 16, 20)
    pick = set(range(start + 300, end + 1, 300))
    if full:
        pick |= set(range(start + 60, end + 1, 60))
    elif not quick:
        pick |= set(range(ts(day, 1, 50), end + 1, 60))
    else:
        for a, z in want:
            pick |= set(range(a - 600, z + 360, 60))
        for h, m in ((9, 25), (12, 40), (15, 45)):
            pick |= set(range(ts(day, h, m), ts(day, h, m) + 31 * 60, 60))
    return sorted(t + 3 for t in pick if start < t <= end)


# ================================================================================================ one day
def run_day(rig, day, label, F: Findings, quick=False, restart_at=None, kill_at=None, want=(), hold=None, passed50=False,
            flatten_at=None, full=False):
    from engine import cme_calendar as C
    from engine.tradovate import LIVE_PHRASE
    print(f"\n== {day}: {label}" + (" (+ Rapid EOD 25K)" if rig.rapid else "") + (" (+ Rapid EOD 50K #2)" if rig.rapid2 else ""),
          flush=True)
    pc = build_pc(rig, day, F)
    body = pc["body"]
    state_path = os.path.join(rig.data, "live_state.json")
    rig.now = ts(day, 18, 0) + 30
    if passed50:                                     # Zlarior's 50K already PASSED (engine/lifecycle: stood down, no orders)
        from engine import lifecycle
        with open(os.path.join(rig.data, lifecycle.FILE), "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "rows": {"lit": {"stage": "passed", "since": rig.now - 86400, "why": "rehearsal: balance >= target",
                                                "label": "Zlarior 50K", "acct": lifecycle.acct_hash(N50), "notified": []}},
                       "events": []}, fh)
    bot, r = make_bot(rig, body, state_path)
    F.check(f"{day} LiveBot started on the ninjatrader adapter", r.get("ok"), r)
    L = lanes(bot)
    want_lanes = {"Zlarior 50K (main)", "Zlarior 25K #2 (b25k_2)", "ATLAS funded 25K (B)"} | (
        {"Rapid 25K LIT lane", "Rapid 25K ATLAS lane"} if rig.rapid else set()) | (
        {"Rapid 50K LIT lane", "Rapid 50K ATLAS lane"} if rig.rapid2 else set())
    names = {k: getattr(ad, "account", None) for k, (_o, ad) in L.items()}
    dis = {k: getattr(ad, "disabled", None) for k, (_o, ad) in L.items() if getattr(ad, "disabled", None)}
    probs = {k: getattr(o, "problem", None) for k, (o, _a) in L.items() if getattr(o, "problem", None)}
    F.check(f"{day} every account routed, enabled (armed + phrase + NINJATRADER_LIVE + allowlist), no problem",
            set(L) == want_lanes and not dis and not probs, {"lanes": sorted(L), "disabled": dis, "problems": probs})
    exp = {"Zlarior 50K (main)": N50, "Zlarior 25K #2 (b25k_2)": N25, "ATLAS funded 25K (B)": NBF,
           "Rapid 25K LIT lane": NR, "Rapid 25K ATLAS lane": NR, "Rapid 50K LIT lane": NR2, "Rapid 50K ATLAS lane": NR2}
    F.check(f"{day} each lane on its own NinjaTrader Name (the 25K #2 eval is never the funded 25K; nothing on ATLAS's locked eval)",
            all(names.get(k) == exp[k] for k in L) and NB_EVAL not in names.values(), names)
    tags = {k: (getattr(ad, "cfg", {}) or {}).get("nt_file_tag", "") for k, (_o, ad) in L.items()}
    sps = {k: (getattr(ad, "cfg", {}) or {}).get("nt_state_path") for k, (_o, ad) in L.items()}
    F.check(f"{day} order-file tags and adapter state files all different", len(set(tags.values())) == len(tags)
            and len(set(sps.values())) == len(sps), {"tags": tags, "state": sps})
    polls = poll_times(day, quick, list(want), full=full)
    errors, hedges, sizes, last_seen = [], [], [], {}
    flat_by = {}
    killed = False
    halt = C.early_close(day)
    flat_mod = C.flat_cut(day, 955)
    t_open_lane, nt_sizes, flattened = {}, [], False
    rapid_two, rapid2_two = [], []
    for t in polls:
        rig.hold = {a: z for a, (f, z) in (hold or {}).items() if t >= f}
        rig.walk(t - 3 - 60)                         # the 1m bar that just closed trades through NinjaTrader
        nxt = rig.o1.get(t - 3)
        if nxt is not None:
            rig.fake.price = nxt                     # the forming bar's first tick: market orders fill here
        rig.now = t
        try:
            bot.poll_once()
        except Exception as e:
            errors.append((hm(t), f"{e.__class__.__name__}: {e}", traceback.format_exc()[-600:]))
        rig.fake.process()
        # ---- MFFU hedging rule: never long on one account and short on another (NinjaTrader's real positions)
        pos = positions(rig)
        if any(q > 0 for q in pos.values()) and any(q < 0 for q in pos.values()):
            hedges.append((hm(t), dict(pos)))
        for a, q in pos.items():
            t_open_lane.setdefault(a, []).append((t, q))
        if rig.rapid:                                # the Rapid: ONE position on the account (LIT lane or ATLAS lane, never both)
            two = rapid_both_open(bot)
            if two:
                rapid_two.append((hm(t), two))
            two2 = rapid_both_open(bot, "rapid2") if rig.rapid2 else None
            if two2:
                rapid2_two.append((hm(t), two2))
        mod = dt.datetime.fromtimestamp(t, ET).hour * 60 + dt.datetime.fromtimestamp(t, ET).minute
        if pos and (mod >= flat_mod and mod < 17 * 60):
            flat_by.setdefault("late", []).append((hm(t), dict(pos)))
        if (t - 3) % 1800 == 0 and (pos or mod in (2 * 60, 9 * 60 + 30, 16 * 60)):
            try:
                nt_sizes.append(ntfy_bytes(bot, t)[:2])
            except Exception as e:
                errors.append((hm(t), f"ntfy payload: {e.__class__.__name__}: {e}", traceback.format_exc()[-600:]))
        if flatten_at and t >= flatten_at and not flattened:
            flattened = True
            flatten_check(rig, bot, day, F)
        if restart_at and t >= restart_at and not getattr(bot, "_rh_restarted", False):
            bot = restart(rig, bot, body, state_path, day, F)
            bot._rh_restarted = True
        if kill_at and t >= kill_at and not killed:
            killed = True
            kill_check(rig, bot, day, F)
            break
    trades_print(bot)
    F.check(f"{day} no poll raised", not errors, errors[:3])
    F.check(f"{day} never long on one account and short on another (MFFU hedging rule), {len(polls)} polls", not hedges, hedges[:5])
    F.check(f"{day} ... not even for an instant between two fills ({len(rig.fills)} fills)", not rig.fill_hedges, rig.fill_hedges[:5])
    if not killed:
        F.check(f"{day} flat on every account from {flat_mod // 60:02d}:{flat_mod % 60:02d} ET" +
                (f" (CME halts {halt // 60:02d}:{halt % 60:02d})" if halt else "") + " to the 16:10 MFFU limit, nothing working",
                not flat_by.get("late") and not working(rig), (flat_by.get("late", [])[:4], working(rig)[:3]))
        if halt:
            late_in = [z for z in entries_of(bot) if int(z[1]) >= ts(day, (halt - 15) // 60, (halt - 15) % 60)]
            F.check(f"{day} no entry in the last 15 min before the {halt // 60:02d}:{halt % 60:02d} halt", not late_in, late_in)
    F.check(f"{day} simulated NinjaTrader saw only well-formed order lines", not rig.fake.errors, rig.fake.errors[:3])
    if flattened:
        after = [z for z in entries_of(bot) if z[1] > getattr(bot, "_rh_flat_t", 0)]
        F.check(f"{day} after the FLATTEN: no new entry on any account for the rest of the day", not after, after)
    sizes = size_checks(bot, day, F)
    rapid_day = None
    if rig.rapid:
        F.check(f"{day} Rapid 25K: one position at a time on its account (LIT lane and ATLAS lane never both open / working)",
                not rapid_two, rapid_two[:5])
        rapid_day = round(sum(p for bk, _t, p, _l in closes_of(bot) if bk == "rapid"), 2)
        F.check(f"{day} Rapid 25K: the day's $ (both lanes) ${rapid_day:,.2f} stays under MFFU's 30% best day "
                f"(${RAPID_BEST_DAY:,.0f} = 30% x $1,500)", rapid_day <= RAPID_BEST_DAY + 1e-9, rapid_day)
    if rig.rapid2:
        F.check(f"{day} Rapid 50K #2: one position at a time on its account", not rapid2_two, rapid2_two[:5])
        r2 = round(sum(p for bk, _t, p, _l in closes_of(bot) if bk == "rapid2"), 2)
        F.check(f"{day} Rapid 50K #2: the day's $ ${r2:,.2f} stays under its 30% best day (${RAPID2_BEST_DAY:,.0f})",
                r2 <= RAPID2_BEST_DAY + 1e-9, r2)
        F.check(f"{day} Rapid 50K #2: the day stays above its -$1,000 soft day (-$1,000 incl. slippage)", r2 >= -1000.0 - 1e-9, r2)
    F.check(f"{day} the ntfy status payload stays under {MAX_STATUS_BYTES:,} bytes (largest {max(nt_sizes or [(0, 0)])[0]:,} of "
            f"{len(nt_sizes)} samples, mid-trade included)", nt_sizes and max(nt_sizes)[0] < MAX_STATUS_BYTES, nt_sizes[-5:])
    life = life_checks(rig, bot, day, F, skip=("lit",) if passed50 else ())
    coach = coach_checks(bot, day, F)
    board = board_checks(rig, bot, day, F)
    return {"day": day, "label": label, "rapid": rig.rapid, "polls": len(polls), "errors": [e[:2] for e in errors],
            "hedges": hedges, "fill_hedges": rig.fill_hedges, "sizes": sizes, "ntfy_bytes": max(nt_sizes or [(0, 0)])[0],
            "life": life, "coach": coach, "board": board, "trades": trade_rows(bot), "rapid_day": rapid_day}


def entries_of(bot) -> list:
    return [(k, int(r.get("t") or 0), r.get("side"), r.get("qty")) for k, (o, _a) in lanes(bot).items()
            for r in (getattr(o, "ledger", None) or []) if r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok") is not False]


def trade_rows(bot) -> list:
    out = []
    for k, (o, _ad) in lanes(bot).items():
        for row in getattr(o, "ledger", None) or []:
            if row.get("side") in ("buy", "sell", "exit"):
                res = row.get("result") or {}
                out.append({"acct": k, "t": hm(row.get("t") or 0), "side": row["side"], "qty": row.get("qty"),
                            "reason": row.get("reason"), "pnl": row.get("pnl"), "ok": res.get("ok"),
                            "error": str(res.get("error") or "")[:200] or None})
    return sorted(out, key=lambda r: r["t"])


def trades_print(bot):
    for r in trade_rows(bot):
        print(f"    {r['acct']:26s} {r['t']} {r['side']:4s} {r['qty'] if r['qty'] is not None else '':>3} "
              + (f"{r['reason']} ${r['pnl']}" if r["side"] == "exit" else "") + ("" if r["ok"] is not False else f" NOT OK: {r['error']}"))
    for ln in list(bot.log)[::-1]:
        if ln["type"] in ("risk", "error") and "sized" not in ln["text"]:
            print(f"    log {hm(ln['t'])} {ln['type']}: {ln['text'][:180]}")


def life_checks(rig, bot, day, F, skip=()):
    """engine/lifecycle: each account's stage after the day = what its own book says (never another account's)."""
    from engine import lifecycle
    lifecycle.tick(bot, int(rig.now), force=True)
    bk = lifecycle.book_for(bot)
    rows = {k: {"stage": v.get("stage"), "label": v.get("label"), "bal": v.get("bal")} for k, v in ((bk.rows if bk else {}) or {}).items()}
    print(f"    lifecycle: " + "; ".join(f"{k} {v['label']} {v['stage']} ${v['bal']}" for k, v in rows.items()))
    want = {"lit": ("eval", "passed"), "x:b25k_2": ("eval", "passed"), "atlas": ("funded", "payout_ready")}
    if rig.rapid:
        want["rapid"] = ("eval", "passed")
    if getattr(rig, "rapid2", False):
        want["rapid2"] = ("eval", "passed")      # the 2nd Rapid's own lifecycle row (never the 1st's)
    bad = {k: rows.get(k) for k, ok in want.items() if k not in skip and (rows.get(k) or {}).get("stage") not in ok}
    # a pass is only right when that account's own book reached its target
    cl = closes_of(bot)
    tgt = {"lit": ("50k", BAL50, 53000.0), "x:b25k_2": ("25k2", 25000.0, 26500.0), "rapid": ("rapid", 25000.0, 26500.0),
           "rapid2": ("rapid2", 50000.0, 53000.0)}
    for k, (b, bal0, tg) in tgt.items():
        if k not in skip and (rows.get(k) or {}).get("stage") == "passed" and bal0 + sum(p for bk_, _t, p, _l in cl if bk_ == b) < tg - 1e-6:
            bad[k] = {"passed but the book is under the target": rows[k]}
    F.check(f"{day} lifecycle: 50K / 25K #2 in eval (or a real pass), ATLAS's 25K funded" + (", Rapid 25K eval" if rig.rapid else ""),
            not bad, {"bad": bad, "rows": rows})
    return rows


def coach_checks(bot, day, F):
    """The payout coach card of the funded 25K (engine/payout_coach on ATLAS's tracker) vs ATLAS's own closed $."""
    from engine import payout_coach as PC
    ab = bot.acct_b
    if ab is None:
        return None
    fv = ab.funded_view(int(bot.clock()))
    c = PC.coach(PC.from_tracker(fv, start=25000.0), "builder25k", today=day)
    mine = round(sum(float(c_[2]) for c_ in ab.all_closes() if str(c_[0]) == day), 2) if hasattr(ab, "all_closes") else \
        round(sum(float(c_[2]) for c_ in ab.closes if str(c_[0]) == day), 2)
    days_traded = 1 if any(str(c_[0]) == day for c_ in ab.closes) else 0
    print(f"    payout coach (funded 25K): {c.get('text')} | balance ${c.get('balance')} profit ${c.get('profit')} days "
          f"{c.get('cycle_days')} request ${c.get('request_today')}")
    ok = (c.get("ok") and abs(float(c["balance"]) - (25000.0 + mine)) < 0.01 and int(c["cycle_days"]) == days_traded
          and float(c["request_today"]) == 0.0 and c["status"] == "not_yet"
          and abs(float(c["need_more"]) - max(0.0, 1100.0 + 250.0 - mine, c["cons_need"] if mine > 0 and not c["cons_ok"] else 0.0)) < 0.01)
    F.check(f"{day} payout coach on the funded 25K = ATLAS's own book (${mine:,.2f} today, day 1: nothing to request yet, "
            f"need ${max(0.0, 1350.0 - mine):,.2f}+ more)", ok, c)
    return {k: c.get(k) for k in ("balance", "profit", "cycle_days", "best_day", "request_today", "need_more", "status", "text")}


def board_checks(rig, bot, day, F):
    """data/board/events.jsonl (engine/board_events): the PC's events of the day, each on the right account."""
    from engine import board_events as BE
    evs = BE.read_jsonl(os.path.join(BE.dirs()[0], BE.EVENTS))
    kinds = [(e.get("kind"), e.get("acct") or e.get("account"), str(e.get("text"))[:90]) for e in evs]
    for k in kinds:
        print(f"    board {k[0]} [{k[1]}] {k[2]}")
    bad = [e for e in evs if e.get("kind") in ("eval_failed", "account_locked", "life_failed", "life_locked", "life_lost", "order_rejected")]
    F.check(f"{day} board events: {len(evs)}, none says failed / locked / rejected on a healthy day", not bad, bad[:3])
    return kinds


def restart(rig, bot, body, state_path, day, F):
    """STOP BOT + START BOT mid-trade (an update / a crash): a NEW LiveBot on the same files must pick every open trade up."""
    before = {k: (getattr(o, "open_t", None) if o is not bot else bot._open_routed) for k, (o, _a) in lanes(bot).items()}
    pos0 = positions(rig)
    n_files = len(rig.fake.files)
    bot.stop()
    rig.now += 20
    nb, r = make_bot(rig, body, state_path)
    after = {k: (getattr(o, "open_t", None) if o is not nb else nb._open_routed) for k, (o, _a) in lanes(nb).items()}
    F.check(f"{day} restart at {hm(rig.now)} with {pos0 or 'no'} open: the new bot starts and every lane remembers its open trade",
            r.get("ok") and before == after, {"before": before, "after": after, "r": r})
    try:
        nb.poll_once()
    except Exception as e:
        F.check(f"{day} first poll after the restart", False, f"{e.__class__.__name__}: {e}")
    rig.fake.process()
    new_lines = [ln for _n, ls in rig.fake.files[n_files:] for ln in ls if ln.startswith("PLACE")]
    F.check(f"{day} restart: no new order placed for an already-open trade, positions unchanged", positions(rig) == pos0 and
            not [ln for ln in new_lines if ";MARKET;" in ln], {"pos": positions(rig), "was": pos0, "placed": new_lines[:4]})
    return nb


def flatten_check(rig, bot, day, F):
    """The phone's FLATTEN (engine/remote_ctl -> LiveBot.flatten_now): every account flat, the bot keeps running, no new entry
    today on any account."""
    pos0 = positions(rig)
    r = bot.flatten_now("REMOTE FLATTEN")
    for _ in range(3):
        rig.fake.process()
        rig.now += 2
        for _k, (_o, ad) in lanes(bot).items():
            try:
                ad.tick()
            except Exception:
                pass
        rig.fake.process()
    F.check(f"{day} FLATTEN at {hm(rig.now)} with {pos0 or 'nothing'} open: every account flat, nothing working, bot still running",
            r.get("ok") and not positions(rig) and not working(rig) and bot.running,
            {"r": r, "pos": positions(rig), "working": working(rig)[:3]})
    bot._rh_flat_t = int(rig.now)


def kill_check(rig, bot, day, F):
    pos0 = positions(rig)
    r = bot.kill_switch()
    for _ in range(3):
        rig.fake.process()
        rig.now += 2
        for _k, (_o, ad) in lanes(bot).items():
            try:
                ad.tick()
            except Exception:
                pass
        rig.fake.process()
    F.check(f"{day} KILL at {hm(rig.now)} with {pos0 or 'nothing'} open: every account flat, nothing working, bot stopped",
            r.get("ok") and not positions(rig) and not working(rig) and not bot.running,
            {"r": r, "pos": positions(rig), "working": working(rig)[:3]})


# ================================================================================================ main
def load_frames(days):
    frames = {}
    lo = ts(min(days), 18, 0) - 70 * 86400
    hi = ts(max(days), 17, 0)
    for sym, tf in (("NQ", "5m"), ("NQ", "1m"), ("ES", "5m"), ("NQ", "1h")):
        df = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_{tf}.csv"))
        df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
        frames[(sym, tf)] = df[(df["time"] >= lo) & (df["time"] < hi)].reset_index(drop=True)
    return frames


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rapid", action="store_true", help="add the Rapid EOD 25K (LIT + ATLAS lanes)")
    ap.add_argument("--rapid2", action="store_true", help="+ a Rapid EOD 50K as Rapid #2 (implies --rapid; day-multirapid)")
    ap.add_argument("--days", default="", help="comma list of yyyy-mm-dd (default: the 5 rehearsal days; any other day "
                                               "with bars in data/ is replayed too, e.g. the newest week)")
    ap.add_argument("--quick", action="store_true", help="polls every minute only around trades / closes, else every 5 min")
    ap.add_argument("--full", action="store_true", help="every minute from 18:00 the evening before (the default starts at 01:50)")
    ap.add_argument("--scenarios", default="all", help="comma list of " + ", ".join(SCENARIOS) + " (all / none)")
    a = ap.parse_args(argv)
    want_days = [x.strip() for x in a.days.split(",") if x.strip()]
    days = [(d, lbl, {}) for d, lbl in DAYS if not want_days or d in want_days]
    days += [(d, "recent day (newest bars)", {}) for d in want_days if d not in dict(DAYS)]   # any other day of data/
    pick = list(SCENARIOS) if a.scenarios == "all" else [] if a.scenarios == "none" else a.scenarios.split(",")
    days += [(SCENARIOS[k][0], SCENARIOS[k][1], SCENARIOS[k][2]) for k in pick]
    F = Findings()
    saved_env = {k: os.environ.get(k) for k in ("NINJATRADER_LIVE", "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER", "NINJATRADER_ALLOW",
                                               "LE_BOARD_DIR", "LE_INBOX_DIR", "LE_LIT_LEARNING")}
    tmp = tempfile.mkdtemp(prefix="le_rehearse_")
    frames = load_frames([d for d, _l, _k in days])
    results = []
    t0 = time.time()
    try:
        for i, (d, label, kw) in enumerate(days):
            dtmp = os.path.join(tmp, f"{i:02d}_{d}")
            rig = Rig(dtmp, frames, rapid=a.rapid, rapid2=a.rapid2)
            os.environ.update({"NINJATRADER_LIVE": "1", "NINJATRADER_FOLDER": rig.folder,
                               "LE_BOARD_DIR": os.path.join(dtmp, "board"), "LE_INBOX_DIR": os.path.join(dtmp, "inbox"),
                               "LE_LIT_LEARNING": os.path.join(dtmp, "no_learning.json")})
            for k in ("NINJATRADER_ACCOUNT", "NINJATRADER_ALLOW"):
                os.environ.pop(k, None)
            rig.install()
            try:
                kw = dict(kw)
                if not kw and d in RESTART:
                    kw["restart_at"] = RESTART[d]
                results.append(run_day(rig, d, label, F, quick=a.quick, full=a.full, **kw))
            finally:
                rig.uninstall()
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(c["ok"] for c in F.checks)
    print(f"\nrehearsal: {n_ok}/{len(F.checks)} checks passed in {time.time() - t0:.0f} s")
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
        key = "with_rapid" if a.rapid else "three_accounts"
        old[key] = {"run": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"), "quick": a.quick, "passed": n_ok, "checks": len(F.checks),
                    "failed": [c for c in F.checks if not c["ok"]], "days": [{k: v for k, v in r.items() if k != "board"} for r in results]}
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(old, fh, indent=1, default=str)
        print(f"-> {os.path.relpath(OUT, ROOT)}")
    except Exception as e:
        print(f"(results not written: {e})")
    return 0 if n_ok == len(F.checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
