"""PC health watchdog (engine/pc_health.py) + the Sunday schedules (Watcher) + the Monday-morning readiness push
(engine/readiness.py). Fake psutil, fake clocks (incl. the DST Sundays 2026-11-01 and 2027-03-14), fake self-test runner,
temp folders only; the real data/ and logs/ files are checked unchanged at the end.

  python -X utf8 -m tests.test_pc_health          (~3 s)
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import pc_health as H, readiness as R  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
REAL = [os.path.join(ROOT, p) for p in (".env.local.ps1", "second_model.json", "live_model.json", "live_model_lit.json",
                                         "data/start_bot.json", "data/autostart.json", "data/push_sent.json", "data/push_prefs.json",
                                         "logs/pc_health.json", "logs/pc_watch.json", "logs/selftest.json")]


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def digest(paths):
    out = {}
    for p in paths:
        try:
            with open(p, "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[p] = None
    return out


def ts(y, mo, d, h, mi):
    return dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()


def lv(ls, key):
    return next((ln["level"] for ln in ls if ln["key"] == key), None)


class FakePs:
    """psutil stand-in: cpu_percent answers from a list, memory / processes from attributes; raise_all = every call raises."""

    def __init__(self, cpu=(10.0,), ram=50.0, rss_mb=500.0, procs=(), raise_all=False):
        self.cpu, self.ram, self.rss_mb, self.procs, self.raise_all = list(cpu), ram, rss_mb, list(procs), raise_all

    def _r(self):
        if self.raise_all:
            raise OSError("access denied")

    def cpu_percent(self, interval=None):
        self._r()
        return self.cpu.pop(0) if len(self.cpu) > 1 else self.cpu[0]

    def virtual_memory(self):
        self._r()
        return SimpleNamespace(percent=self.ram, used=self.ram / 100 * 8 * 2 ** 30, total=8 * 2 ** 30)

    def Process(self):
        self._r()
        me = self
        return SimpleNamespace(memory_info=lambda: (me._r(), SimpleNamespace(rss=me.rss_mb * 2 ** 20))[1])

    def process_iter(self, attrs=None):
        self._r()
        self.scans = getattr(self, "scans", 0) + 1
        me = self

        def proc(n, mb):
            def mi():
                live = dict(me.procs)
                if n not in live:
                    raise ProcessLookupError(n)          # psutil.NoSuchProcess stand-in: that process is gone
                return SimpleNamespace(rss=live[n] * 2 ** 20)
            return SimpleNamespace(info={"name": n, "memory_info": SimpleNamespace(rss=mb * 2 ** 20)}, memory_info=mi)
        return [proc(n, mb) for n, mb in self.procs]


def t_lines():
    ok = H.lines({"cpu_pct": 20, "ram_pct": 60, "ram_used_gb": 4.8, "ram_total_gb": 8, "disk_free_gb": 40,
                  "nt": {"running": True, "mb": 900, "market_open": True, "routes": True}, "bot_mb": 600, "bot_base_mb": 550,
                  "onedrive": {"files": [], "in_onedrive": False}, "clock": {"drift": 0.3, "max": 5.0},
                  "poll": {"med15": 800, "med_prev": 750}})
    check("all normal: 8 lines, every one green", len(ok) == 8 and all(ln["level"] == "green" for ln in ok) and H.level_of(ok) == "green", ok)
    cases = [("cpu", {"cpu_pct": 88}, "amber"), ("cpu", {"cpu_pct": 97}, "red"), ("ram", {"ram_pct": 90}, "amber"),
             ("ram", {"ram_pct": 96}, "red"), ("disk", {"disk_free_gb": 8}, "amber"), ("disk", {"disk_free_gb": 1.5}, "red"),
             ("nt", {"nt": {"running": False, "market_open": True, "routes": True}}, "red"),
             ("nt", {"nt": {"running": False, "market_open": False, "routes": True}}, "amber"),
             ("nt", {"nt": {"running": False, "market_open": True, "routes": False}}, "amber"),
             ("nt", {"nt": {"running": True, "mb": 3000}}, "amber"), ("nt", {"nt": {"running": True, "mb": 4500}}, "red"),
             ("bot_mem", {"bot_mb": 1300, "bot_base_mb": 600}, "amber"), ("bot_mem", {"bot_mb": 2300, "bot_base_mb": 600}, "red"),
             ("bot_mem", {"bot_mb": 2100}, "amber"), ("bot_mem", {"bot_mb": 800, "bot_base_mb": 700, "bot_rate_mbh": 250}, "amber"),
             ("onedrive", {"onedrive": {"files": ["engine/x-SURFACE.py"]}}, "amber"),
             ("onedrive", {"onedrive": {"files": ["data/live_state (1).json"]}}, "red"),
             ("onedrive", {"onedrive": {"files": [], "in_onedrive": True}}, "amber"),
             ("clock", {"clock": {"drift": 3.0, "max": 5.0}}, "amber"), ("clock", {"clock": {"drift": -6.0, "max": 5.0}}, "red"),
             ("poll", {"poll": {"med15": 6000, "med_prev": 5800}}, "amber"), ("poll", {"poll": {"med15": 25000}}, "red"),
             ("poll", {"poll": {"med15": 3000, "med_prev": 900}}, "amber"), ("poll", {"poll": {"med15": 1500, "med_prev": 600}}, "green")]
    bad = [(k, f, want, lv(H.lines(f), k)) for k, f, want in cases if lv(H.lines(f), k) != want]
    check(f"thresholds: {len(cases)} cases (CPU / RAM / disk / NinjaTrader / bot memory / OneDrive / clock / poll trend)", not bad, bad)
    t = {ln["key"]: ln["text"] for ln in H.lines({"nt": {"running": False, "market_open": True, "routes": True},
                                                   "clock": {"drift": 7.0, "max": 5.0}, "onedrive": {"files": ["data/live_state (1).json"]}})}
    check("red lines say the one fix", "open it now" in t["nt"] and "Sync the clock" in t["clock"] and "tell Claude" in t["onedrive"], t)
    check("missing facts = no line (skipped, never an error)", H.lines({}) == [])


def t_sampler():
    tmp = tempfile.mkdtemp(prefix="le_t_pch_")
    try:
        ps = FakePs(cpu=(0, 50, 90, 95, 99, 98, 97), ram=91, rss_mb=500, procs=[("NinjaTrader.exe", 1200), ("chrome.exe", 300)])
        bot = SimpleNamespace(running=True, cfg={"adapter": "ninjatrader"}, health={}, last_poll=None)
        t0 = ts(2026, 10, 27, 10, 0)           # a Tuesday in the session
        s = H.Sampler(bot, ps=ps, root=tmp, is_windows=True, host="SURFACE-7", t0=t0)
        for i in range(5):
            b = s.block(t0 + 60 * i)
        check("CPU: the median of the last 5 samples (one busy minute is not an alarm)", s.facts(t0 + 300)["cpu_pct"] >= 95
              and lv(b["lines"], "cpu") in ("amber", "red"), list(s.cpu))
        check("RAM 91% -> amber", lv(b["lines"], "ram") == "amber")
        f = s.facts(t0 + 400)
        check("NinjaTrader.exe found with its memory (Windows)", f["nt"]["running"] and f["nt"]["mb"] == 1200 and f["nt"]["market_open"]
              and f["nt"]["routes"], f["nt"])
        n0 = ps.scans
        ps.procs = [("NinjaTrader.exe", 1500), ("chrome.exe", 300)]
        f = s.facts(t0 + 420)
        check("NinjaTrader: between full scans only its own process is asked (memory 1,500 MB, no new process-list read)",
              ps.scans == n0 and f["nt"]["mb"] == 1500, (ps.scans, n0, f["nt"]))
        ps.procs = [("chrome.exe", 300)]
        check("NinjaTrader not running in the session while the bot routes -> red (its process gone = scan at once)",
              lv(s.block(t0 + 460)["lines"], "nt") == "red" and ps.scans == n0 + 1)
        s.facts(t0 + 470)
        check("not found: the next full scan only after 60 s", ps.scans == n0 + 1)
        s.facts(t0 + 530)
        check("... and then again", ps.scans == n0 + 2)
        check("bot memory: no growth figure before the 10-minute warm-up", s.facts(t0 + 500).get("bot_base_mb") is None)
        sat = ts(2026, 10, 31, 12, 0)
        check("... on a Saturday (market closed) -> amber", lv(H.Sampler(bot, ps=ps, root=tmp, is_windows=True, t0=t0).block(sat)["lines"], "nt") == "amber")
        s.facts(t0 + 700)
        ps.rss_mb = 1300
        b = s.block(t0 + 3600)
        check("bot memory: base taken after the warm-up, +800 MB -> amber", s.base_mb == 500 and lv(b["lines"], "bot_mem") == "amber"
              and "+800 MB since it started" in next(ln["text"] for ln in b["lines"] if ln["key"] == "bot_mem"), b["lines"])
        ps.rss_mb = 2300
        check("bot memory: +1.8 GB -> red", lv(s.block(t0 + 7300)["lines"], "bot_mem") == "red")
        s2 = H.Sampler(bot, ps=FakePs(procs=[]), root=tmp, is_windows=False, t0=t0)
        check("not Windows: the NinjaTrader line is skipped", "nt" in s2.block(t0)["skipped"] and lv(s2.block(t0)["lines"], "nt") is None)
        s3 = H.Sampler(bot, ps=None, root=tmp, is_windows=True, t0=t0)
        b3 = s3.block(t0)
        check("no psutil: CPU / RAM / NinjaTrader / bot memory skipped, disk + OneDrive still there",
              {"cpu", "ram", "nt", "bot_mem"} <= set(b3["skipped"]) and lv(b3["lines"], "disk") and lv(b3["lines"], "onedrive")
              and b3["psutil"] is False, b3)
        s4 = H.Sampler(SimpleNamespace(), ps=FakePs(raise_all=True), root=tmp, is_windows=True, t0=t0)
        b4 = s4.block(t0)
        check("psutil raising on every call (access denied): no exception, lines skipped", isinstance(b4, dict)
              and {"cpu", "ram", "bot_mem"} <= set(b4["skipped"]), b4)

        class Boom:
            @property
            def health(self):
                raise RuntimeError("x")
            running = True
            last_poll = 5
        b5 = H.Sampler(Boom(), ps=FakePs(), root=tmp, is_windows=False, t0=t0).block(t0)
        check("a bot whose health raises: no exception, no poll line", isinstance(b5, dict) and lv(b5["lines"], "poll") is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_poll_clock():
    from engine import guards
    bot = SimpleNamespace(running=True, cfg={}, health={"poll_ms": 800}, last_poll=0)
    s = H.Sampler(bot, ps=None, root=ROOT, is_windows=False, t0=0)
    s._od = {"t": 10 ** 12, "files": []}            # no OneDrive scan of the repo in this part
    t0 = ts(2026, 10, 27, 9, 0)
    for i in range(75):
        bot.last_poll = t0 + 60 * i
        bot.health = {"poll_ms": 800 if i < 60 else 3200}
        f = s.facts(t0 + 60 * i)
    check("poll: 15-min median vs the hour before", f["poll"]["med15"] == 3200 and f["poll"]["med_prev"] == 800, f.get("poll"))
    check("poll 0.8 s -> 3.2 s: amber (rising), says where to look", lv(H.lines(f), "poll") == "amber"
          and "Bot loop" in next(ln["text"] for ln in H.lines(f) if ln["key"] == "poll"))
    n = len(s.polls)
    s.facts(t0 + 60 * 75)
    check("poll: an unchanged last_poll adds no sample", len(s.polls) == n)
    bot.running = False
    bot.last_poll = t0 + 60 * 80
    s.facts(t0 + 60 * 80)
    check("poll: a stopped bot adds no sample", len(s.polls) == n)
    saved = dict(guards._CLOCK)
    try:
        guards._CLOCK.update(drift=None)
        check("clock: never probed -> no line (the bot's own probe; nothing probed here)", "clock" not in s.facts(t0))
        guards._CLOCK.update(drift=6.2, ok_t=t0, max=5.0)
        f = s.facts(t0)
        check("clock: the guard's drift 6.2 s > 5 s -> red", lv(H.lines(f), "clock") == "red", f.get("clock"))
    finally:
        guards._CLOCK.clear()
        guards._CLOCK.update(saved)


def t_onedrive():
    tmp = tempfile.mkdtemp(prefix="le_t_od_")
    try:
        for p in ("data/live_state (1).json", "data/lit_journal-SURFACE-7.jsonl", "engine/live-DESKTOP-AB12.py", "data/news/hub (2).json",
                  "data/nt_bars/MNQ (1).csv", "engine/ok.py", "data/live_state.json", "tools/a (copy).txt", "STRATEGY-SURFACE-7.md"):
            fp = os.path.join(tmp, *p.split("/"))
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            open(fp, "w").write("x")
        got = H.onedrive_conflicts(tmp, host="SURFACE-7")
        want = ["STRATEGY-SURFACE-7.md", "data/lit_journal-SURFACE-7.jsonl", "data/live_state (1).json", "data/news/hub (2).json",
                "engine/live-DESKTOP-AB12.py"]
        check("OneDrive / Windows conflict copies found (data/ two levels, the bar archive skipped), normal files not", got == want, got)
        check("a conflict copy in data/ -> red", lv(H.lines({"onedrive": {"files": got}}), "onedrive") == "red")
        check("capped scan (max entries) never raises", isinstance(H.onedrive_conflicts(tmp, max_entries=2), list))
        check("bot folder inside OneDrive detected", H.in_onedrive(r"C:\Users\me\OneDrive\Documents\nq-liquidity-engine")
              and not H.in_onedrive(r"C:\nq-liquidity-engine"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_red_push():
    st = {}
    red = {"lines": [{"key": "disk", "label": "Disk space", "level": "red", "text": "1.2 GB free"}]}
    green = {"lines": [{"key": "disk", "label": "Disk space", "level": "green", "text": "40 GB free"}]}
    now = ts(2026, 10, 27, 11, 0)
    check("one red sample: no push yet (two in a row)", H.red_notices(red, green, st, now) == [])
    n = H.red_notices(red, red, st, now)
    check("two red samples: one push (kind pc_health, key per issue per ET day)", len(n) == 1 and n[0]["kind"] == "pc_health"
          and n[0]["key"] == "pchealth:disk:2026-10-27" and "Disk space" in n[0]["title"], n)
    check("same issue, same day: no second push", H.red_notices(red, red, st, now + 3600) == [])
    check("next ET day: one again", len(H.red_notices(red, red, st, ts(2026, 10, 28, 0, 5))) == 1)
    os.environ["LE_PC_HEALTH_PUSH"] = "0"
    try:
        check("LE_PC_HEALTH_PUSH=0: none", H.red_notices(red, red, {}, now) == [])
    finally:
        os.environ.pop("LE_PC_HEALTH_PUSH", None)


class FakeSampler:
    def __init__(self):
        self.level = "green"

    def block(self, now):
        return {"t": int(now), "level": self.level, "lines": [{"key": "cpu", "label": "CPU", "level": self.level, "text": "CPU"}], "skipped": []}


class FakeRunner:
    def __init__(self, result=None):
        self.started, self.mode, self.result = [], None, result

    def busy(self):
        return self.mode is not None

    def start(self, mode="manual", on_done=None, wait=False):
        self.started.append(mode)
        if on_done is not None and self.result is not None:
            on_done({**self.result, "mode": mode})
        return {"ok": True, "started": True, "mode": mode}


def watcher(tmp, runner, sent, clock_t, ver="v2", last=None, started_at=0.0, ready=None):
    return H.Watcher(SimpleNamespace(running=False), clock=lambda: clock_t[0], state_path=os.path.join(tmp, "w.json"),
                     block_path=os.path.join(tmp, "b.json"), sampler=FakeSampler(), runner=runner, sender=sent.append,
                     readiness_fn=ready or (lambda bot, now: {"key": f"readiness:{dt.datetime.fromtimestamp(now, ET).date()}", "kind": "readiness",
                                                              "title": "Ready for Monday", "body": "x"}),
                     version_fn=lambda: ver, selftest_last=lambda: (last or {"version": ver}), started_at=started_at)


def t_schedules():
    tmp = tempfile.mkdtemp(prefix="le_t_sch_")
    try:
        for label, (y, mo, d) in (("Sun 2026-10-25 (EDT)", (2026, 10, 25)), ("Sun 2026-11-01 (clocks went back at 02:00: EST)", (2026, 11, 1)),
                                  ("Sun 2027-03-14 (clocks went forward at 02:00: EDT)", (2027, 3, 14))):
            sent, rn, clk = [], FakeRunner(), [0.0]
            w = watcher(tmp, rn, sent, clk)
            for f in os.listdir(tmp):
                os.remove(os.path.join(tmp, f))
            did = []
            for hh, mm in ((15, 29), (15, 30), (15, 31), (17, 29), (17, 30), (17, 31), (18, 29)):
                clk[0] = ts(y, mo, d, hh, mm)
                did.append((hh, mm, w.tick()["did"]))
            check(f"{label}: self-test starts at 15:30 ET New York time, once", rn.started == ["sunday"] and did[1][2] and not did[0][2]
                  and not did[2][2], did)
            check(f"{label}: readiness pushed at 17:30 ET, once", [p["key"] for p in sent] == [f"readiness:{y:04d}-{mo:02d}-{d:02d}"]
                  and not did[3][2] and did[4][2], sent)
        # the UTC hour of 15:30 ET moves with the clock change: 19:30 UTC is 15:30 on Oct 25 but 14:30 on Nov 1
        sent, rn, clk = [], FakeRunner(), [dt.datetime(2026, 11, 1, 19, 30, tzinfo=dt.timezone.utc).timestamp()]
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        w = watcher(tmp, rn, sent, clk)
        w.tick()
        r1 = list(rn.started)
        clk[0] = dt.datetime(2026, 11, 1, 20, 30, tzinfo=dt.timezone.utc).timestamp()
        w.tick()
        check("DST Sunday: 19:30 UTC (= 14:30 EST) nothing, 20:30 UTC (= 15:30 EST) the self-test", r1 == [] and rn.started == ["sunday"],
              (r1, rn.started))
        # a busy runner at 15:30: tried again the next minute
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        sent, rn, clk = [], FakeRunner(), [ts(2026, 11, 8, 15, 30)]
        rn.mode = "manual"
        w = watcher(tmp, rn, sent, clk)
        w.tick()
        rn.mode = None
        clk[0] = ts(2026, 11, 8, 15, 31)
        w.tick()
        check("a self-test already running at 15:30: the Sunday one starts the next minute", rn.started == ["sunday"], rn.started)
        # results pushed through the runner's on_done
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        sent, clk = [], [ts(2026, 11, 8, 15, 30)]
        rn = FakeRunner({"t": int(clk[0]), "failed": 1, "total": 27, "passed": 26, "version": "abc1234", "dur_s": 70,
                         "first": [{"key": "heartbeat", "label": "Heartbeat push", "why": "x"}], "rows": [{"key": "heartbeat", "ok": False}]})
        watcher(tmp, rn, sent, clk).tick()
        check("Sunday result with a failure -> one push 'PC self-test: 1 failed (Heartbeat push)'",
              [p["title"] for p in sent] == ["PC self-test: 1 failed (Heartbeat push)"], sent)
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        sent = []
        rn = FakeRunner({"t": int(clk[0]), "failed": 0, "total": 27, "passed": 27, "version": "abc1234", "dur_s": 70, "ok": True})
        watcher(tmp, rn, sent, clk).tick()
        check("Sunday result all green -> the short 'all green' push (kind selftest_ok)", [p["kind"] for p in sent] == ["selftest_ok"], sent)
        # baseline after a server start
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        t_eve = ts(2026, 10, 27, 20, 0)
        sent, rn, clk = [], FakeRunner(), [t_eve + 60]
        w = watcher(tmp, rn, sent, clk, ver="v2", last={"version": "v1"}, started_at=t_eve)
        w.tick()
        r0 = list(rn.started)
        clk[0] = t_eve + 400
        w.tick()
        clk[0] = t_eve + 500
        w.tick()
        check("baseline: a version with no result -> one self-test 5+ min after the start (Tue 20:00 ET), once", r0 == [] and rn.started == ["baseline"],
              (r0, rn.started))
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        rn, t_day = FakeRunner(), ts(2026, 10, 27, 10, 0)
        w = watcher(tmp, rn, [], [t_day + 600], ver="v3", last={"version": "v1"}, started_at=t_day)
        w.tick()
        check("baseline: never in 01:50-16:00 ET on a weekday", rn.started == [], rn.started)
        rn = FakeRunner()
        watcher(tmp, rn, [], [t_eve + 900], ver="v1", last={"version": "v1"}, started_at=t_eve).tick()
        check("baseline: not when this version already has a result", rn.started == [], rn.started)
        # red health line pushes through the watcher, the block lands in its file
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        sent, clk = [], [t_eve]
        w = watcher(tmp, FakeRunner(), sent, clk, last={"version": "v2"})
        w.sampler.level = "red"
        w.tick()
        clk[0] += 60
        w.tick()
        clk[0] += 60
        w.tick()
        check("watcher: a red line twice in a row -> one pc_health push", [p["kind"] for p in sent] == ["pc_health"], sent)
        check("watcher: the block is written for the heartbeat", json.load(open(os.path.join(tmp, "b.json")))["level"] == "red")
        sv = H.WATCHER
        try:
            H.WATCHER = w
            w.block = {**w.block, "t": int(__import__("time").time())}     # the heartbeat reads it on the real clock
            from engine import heartbeat as HB
            hb = HB._pc_health()
            check("heartbeat 'pc_health' block from the watcher (level + lines, small)", hb and hb["level"] == "red" and len(json.dumps(hb)) < 3000, hb)
            w.block = {**w.block, "t": 1}
            check("heartbeat: a block older than 1 h is left out", H.hb_block(path=os.path.join(tmp, "none.json")) is None)
        finally:
            H.WATCHER = sv
        src = open(os.path.join(ROOT, "engine", "heartbeat.py"), encoding="utf-8").read()
        check("heartbeat payload: optional selftest + pc_health keys (absent until they exist)",
              '**_opt("selftest", _selftest())' in src and '**_opt("pc_health", _pc_health())' in src)
        for k, v in (("LE_PC_WATCH", "0"), ("LE_NO_AUTOSTART", "1"), ("LE_SELFTEST_CHILD", "1")):
            old = os.environ.get(k)
            os.environ[k] = v
            try:
                ok = H.Watcher(None, sampler=FakeSampler(), runner=FakeRunner(), state_path=os.path.join(tmp, "x.json"),
                               block_path=os.path.join(tmp, "y.json")).start() is False
            finally:
                if old is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = old
            check(f"watcher thread never starts with {k}={v}", ok)
        srv = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
        check("server.py: one Watcher on the bot, registered, started with the other threads",
              "PCWATCH = _pch.Watcher(BOT)" in srv and "_pch.WATCHER = PCWATCH" in srv and "    PCWATCH.start()" in srv)
        lv_src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
        check("nothing in the trading poll (engine/live.py does not know pc_health / pc_selftest)",
              "pc_health" not in lv_src and "pc_selftest" not in lv_src)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ev(y, mo, d, h, mi, name, impact="high", cur="USD"):
    return {"t": int(ts(y, mo, d, h, mi)), "event": name, "impact": impact, "currency": cur}


GOOD = {"version": "abc1234", "selftest": {"t": int(ts(2026, 11, 1, 15, 32)), "ok": True, "failed": 0, "total": 30, "passed": 30,
                                           "dur_s": 74.0, "version": "abc1234"},
        "run_switch": True, "running": True, "update": {"result": "up_to_date"},
        "board": {"lit": {"room": 1640.0, "session": 3, "sessions": 10, "status": "open"},
                  "atlas": {"room": 1000.0, "session": 1, "sessions": 10, "status": "open"}},
        "blitz": {"on": False}, "events": [ev(2026, 11, 4, 14, 0, "FOMC Statement"), ev(2026, 11, 6, 8, 30, "Non-Farm Employment Change"),
                                           ev(2026, 11, 3, 10, 0, "ISM Services PMI", "medium"), ev(2026, 11, 5, 3, 0, "ECB Rate", cur="EUR"),
                                           ev(2026, 11, 7, 10, 0, "Saturday thing")]}


def t_readiness():
    now = ts(2026, 11, 1, 17, 30)
    r = R.build(GOOD, now)
    L = r["lines"]
    check("readiness: all good -> 'Ready for Monday'", r["title"] == "Ready for Monday" and r["level"] == "good" and not r["problems"], r)
    check("line: version + self-test", L[0].startswith("Version abc1234 · self-test all 30 green in 74.0 s"), L[0])
    check("line: Run switch is ON (bot running)", L[1] == "Run switch is ON (bot running)", L[1])
    check("lines: both accounts' room to the floor and eval day N of 10, BLITZ off",
          L[2] == "Zlarior 50K: $1,640 room to the floor, eval day 3 of 10" and L[3] == "ATLAS 25K: $1,000 room to the floor, eval day 1 of 10"
          and L[4] == "BLITZ 25K: off (paper shadow only)", L[2:5])
    check("news: high-impact USD events Mon-Fri only, time-ordered (medium / EUR / Saturday left out)",
          L[5] == "News: Wed 14:00 FOMC Statement; Fri 08:30 Non-Farm Employment Change", L[5])
    check("early closes: normal hours this week", L[6] == "This week: normal hours (no early close)", L[6])
    check("DST Sunday 2026-11-01: 'Clocks went back one hour this morning (to EST)'",
          L[7].startswith("Clocks went back one hour this morning (to EST)") and "New York time" in L[7], L[7:])
    p = R.notice(None, now, facts=GOOD)
    check("push: kind readiness, key per Sunday, body under 600 chars", p["kind"] == "readiness" and p["key"] == "readiness:2026-11-01"
          and len(p["body"]) <= 600 and p["body"].startswith("Version abc1234"), p)
    check("DST a week ahead (Sun 2026-10-25): 'go back one hour on Sun Nov 01'", "go back one hour on Sun Nov 01" in (R.dst_note(ts(2026, 10, 25, 17, 30)) or ""),
          R.dst_note(ts(2026, 10, 25, 17, 30)))
    check("DST Sunday 2027-03-14: 'went forward one hour this morning (to EDT)'",
          (R.dst_note(ts(2027, 3, 14, 17, 30)) or "").startswith("Clocks went forward one hour this morning (to EDT)"))
    check("no clock change on Sun 2026-11-08: no DST line", R.dst_note(ts(2026, 11, 8, 17, 30)) is None)
    th = R.build({**GOOD, "events": []}, ts(2026, 11, 22, 17, 30))["lines"]
    check("Thanksgiving week: Thu 13:00 and Fri 13:15 early closes with the last entry time; no high-impact news",
          th[6] == "This week: Thu Nov 26 early close 13:00 ET (no new entry after 12:45); Fri Nov 27 early close 13:15 ET (no new entry after 13:00)"
          and th[5] == "News: none high-impact", th[5:7])
    xm = R.build(GOOD, ts(2026, 12, 20, 17, 30))["lines"]
    check("Christmas week: Thu Dec 24 early close, Fri Dec 25 closed", "Thu Dec 24 early close 13:15 ET" in xm[6] and "Fri Dec 25 closed" in xm[6], xm[6])
    bad = R.build({**GOOD, "run_switch": False, "selftest": {**GOOD["selftest"], "failed": 2, "ok": False,
                                                              "first": [{"label": "Start page", "why": "x"}, {"label": "Heartbeat push"}]}}, now)
    check("problems first in the title: self-test failure, Run switch OFF (+1)", bad["title"] == "Before Monday: self-test: Start page (+1)"
          and bad["level"] == "warn" and "Run switch is OFF: press Run on the dashboard before 18:00 ET" in bad["lines"], bad)
    none = R.build({}, now)
    check("no facts at all: still a push, every part 'unknown'", none["title"].startswith("Before Monday") and "Run switch unknown" in none["lines"]
          and "Zlarior 50K: unknown (no board)" in none["lines"] and "News: unknown" in none["lines"], none)
    check("BLITZ: Sim test / set not armed / armed", R.blitz_line({"on": True, "sim": True, "name": "Sim102"}) == "BLITZ 25K: Sim test on Sim102"
          and "not armed" in R.blitz_line({"on": True, "name": "MFFUEVBLDR3"}) and R.blitz_line({"on": True, "armed": True, "name": "MFFUEVBLDR3"})
          == "BLITZ 25K: ARMED on MFFUEVBLDR3")
    check("accounts: funded day, eval passed, not set up", R.account_line("Zlarior 50K", {"room": 2100, "session": 4, "sessions": None})
          == "Zlarior 50K: $2,100 room to the floor, funded day 4" and R.account_line("ATLAS 25K", {"status": "passed", "room": 900})
          == "ATLAS 25K: eval PASSED ($900 room)" and R.account_line("ATLAS 25K", {"status": "not set up"}) == "ATLAS 25K: not set up")
    old = R.build({**GOOD, "selftest": {**GOOD["selftest"], "t": int(now - 9 * 86400)}}, now)
    check("a self-test older than 8 days is a problem ('no self-test this week')", "no self-test this week" in old["problems"], old["problems"])
    f = R.gather(None, now, news_fn=lambda n: [])
    check("gather() with no bot: no exception, news from the injected source, no board", f.get("events") == [] and "board" not in f
          and "version" in f, sorted(f))
    buf = io.StringIO()
    from engine import readiness as RR
    saved = RR.gather
    RR.gather = lambda bot, now, news_fn=None: dict(GOOD)
    try:
        with contextlib.redirect_stdout(buf):
            H.main(["--readiness"])
    finally:
        RR.gather = saved
    check("CLI: python -m engine.pc_health --readiness prints the push (no send without --send)", buf.getvalue().startswith("Ready for Monday\nVersion abc1234"),
          buf.getvalue()[:200])


def t_cli():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        H.main(["--json"])
    b = json.loads(buf.getvalue())
    check("CLI --json on this machine (real psutil): disk / OneDrive lines, nothing red from the scan",
          lv(b["lines"], "disk") is not None and lv(b["lines"], "onedrive") in ("green", "amber") and "nt" in b["skipped"], b)


def main():
    before = digest(REAL)
    for t in (t_lines, t_sampler, t_poll_clock, t_onedrive, t_red_push, t_schedules, t_readiness, t_cli):
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{t.__name__} raised {e.__class__.__name__}: {e}", False)
    check("the real data/, logs/pc_health.json, logs/pc_watch.json, .env.local.ps1, second_model.json, live_model*.json did not change",
          digest(REAL) == before)
    n = sum(RES)
    print(f"pc health: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
