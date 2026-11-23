"""FAULT INJECTION (night-faults 2026-11-23): nothing silently stops trading. Fakes and temp folders only: no real NinjaTrader,
no phone, no order. Handoff table: research/handoff/2026-11-23/FAULTS.md.

    python -X utf8 -m tests.test_faults

 a. LE_BarFeed file: missing / empty / truncated / junk line (also FIRST in an appended chunk) / duplicate / out of order / NaN
 b. order file: the publish refused (PermissionError) every try -> ok False + the reason, nothing left in le_outbox; once ->
    the retry writes it
 c. NinjaTrader adapter state: save on a full disk -> logged + ONE alert per 30 min; corrupt / empty / odd state -> blocked
    (state_problem), never read as flat
 d. LiveBot state: save on a full disk -> logged, the real bot pushes once per 30 min; corrupt live_state.json -> clean start
 e. corrupt data/accounts.json / rapid.json / account_b.json -> the same safe default (never armed) + a fault note; missing ->
    no note
 f. one lane's exception (ATLAS, a Rapid ATLAS, account C, the fleet, the keep-alive, one extra account) never raises out
 g. internet down: chat alerts never block the poll (threaded), alerts.send never raises
 h. the history export torn mid-session: the last good copy is used (same bars), with no good copy it raises as before
"""
import builtins
import io
import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import ninjatrader as NT, live as L, fault_note as FN  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append((name, bool(cond)))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


HDR = "time,open,high,low,close,volume\n"
GOOD = HDR + "".join(f"{1795000000 + 60 * i},1,2,0.5,1.5,10\n" for i in range(5))


def t_feed():
    print("a. the bar file", flush=True)
    d = tempfile.mkdtemp()
    f = os.path.join(d, "MNQ_1m.csv")
    B = NT.NinjaTraderBars(d)
    check("a1. missing file -> None (the caller says 'no feed file', entries blocked)", B.load(f) is None)
    seq = [("empty", "", 0), ("header only", HDR, 0), ("good", GOOD, 5), ("a torn last line (not parsed yet)", GOOD + "1795000300,1,2", 5),
           ("junk FIRST in the appended chunk", GOOD + "xx,yy,zz\n", 5), ("then a new bar", GOOD + "xx,yy,zz\n1795000300,1,2,0.5,1.5,10\n", 6),
           ("a duplicate bar (last kept)", GOOD + f"{1795000240},9,9,9,9,9\n", 5),
           ("out of order", HDR + "".join(f"{1795000000 + 60 * i},1,2,0.5,1.5,10\n" for i in (0, 2, 1, 4, 3)), 5),
           ("a NaN row", GOOD + "1795000300,nan,2,0.5,1.5,10\n", 5), ("binary junk", "\x00\x00\x00", 0)]
    for nm, body, n in seq:
        with open(f, "w") as fh:
            fh.write(body)
        try:
            df = B.load(f)
            ok = df is not None and len(df) == n and df["time"].is_monotonic_increasing and df["time"].is_unique
        except Exception as e:  # noqa: BLE001
            ok, df = False, e
        check(f"a2. {nm}: {n} clean bars, never raises", ok, df)


def _adapter(d, **kw):
    NT._FakeNT(d)
    cfg = {"nt_folder": d, "nt_account": "Sim101", "nt_instrument": "MNQ 12-26", "armed": True,
           "nt_state_path": os.path.join(d, "st.json"), **kw}
    return NT.NinjaTraderAdapter(cfg)


def t_oif():
    print("b. the order file", flush=True)
    d = tempfile.mkdtemp()
    ad = _adapter(d)
    ad._global_kill = True
    ad._sleep = lambda s: None
    rp, sl = NT._publish, NT.time.sleep
    NT.time.sleep = lambda s: None
    try:
        NT._publish = lambda a, b: (_ for _ in ()).throw(PermissionError(13, "locked"))
        r = ad._write_oif(["CANCELALLORDERS;;;;;;;;;;;;"], "probe")
        box = os.path.join(d, "le_outbox")
        check("b1. publish refused every try: ok False with the reason, no copy left in le_outbox", r.get("ok") is False
              and "PermissionError" in r.get("error", "") and not os.listdir(box) and "PermissionError" in (ad.last_error or ""), (r, os.listdir(box)))
        n = {"c": 0}

        def once(a, b):
            if n["c"] == 0:
                n["c"] += 1
                raise PermissionError(13, "locked")
            return rp(a, b)
        NT._publish = once
        r = ad._write_oif(["CANCELALLORDERS;;;;;;;;;;;;"], "probe")
        check("b2. locked once: the retry writes it", r.get("ok") is True and os.path.exists(r["path"]), r)
    finally:
        NT._publish, NT.time.sleep = rp, sl


def t_adapter_state():
    print("c. the adapter's state file", flush=True)
    d = tempfile.mkdtemp()
    alerts = []
    ad = _adapter(d)
    ad._alert_fn = alerts.append
    t = [1795000000.0]
    ad.clock = lambda: t[0]
    ro = builtins.open

    def full(p, *a, **k):
        if str(p).endswith(".tmp"):
            raise OSError(28, "No space left on device")
        return ro(p, *a, **k)
    builtins.open = full
    try:
        ad._save()
        t[0] += 600
        ad._save()
        t[0] += 1300
        ad._save()
    finally:
        builtins.open = ro
    check("c1. a full disk: last_error says it, ONE alert, again only after 30 min", len(alerts) == 2 and "No space" in alerts[0]
          and "CLEAN_STORAGE" in alerts[0] and "state save failed" in (ad.last_error or ""), alerts)
    for nm, body in (("corrupt", "{bad json"), ("empty", ""), ("an odd / older shape", json.dumps({"version": 0, "legs": "x"}))):
        with open(os.path.join(d, "st.json"), "w") as fh:
            fh.write(body)
        a2 = _adapter(d)
        check(f"c2. {nm} state: new entries blocked (state_problem), never read as flat", bool(a2.state_problem), a2.state_problem)


def _bot(tmp):
    b = L.LiveBot()
    b.cfg = {"sym": "NQ", "tf": "5m"}
    b.state_path = os.path.join(tmp, "live_state.json")
    return b


def t_bot_state():
    print("d. the bot's state file", flush=True)
    tmp = tempfile.mkdtemp()
    b = _bot(tmp)
    pushed = []
    b._problem_bg = pushed.append
    ro = builtins.open

    def full(p, *a, **k):
        if str(p).endswith(".tmp"):
            raise OSError(28, "No space left on device")
        return ro(p, *a, **k)
    builtins.open = full
    try:
        b._save_state()
    finally:
        builtins.open = ro
    check("d1. a full disk (test bot): logged in health, no push (not the real bot), never raises",
          "No space" in str(b.health.get("last_error")) and not pushed, b.health.get("last_error"))
    real = L.STATE_PATH
    L.STATE_PATH = b.state_path                 # this bot plays the real one (its file is still the temp one)
    try:
        t = [1795000000]
        b.clock = lambda: t[0]
        builtins.open = full
        try:
            b._save_state()
            t[0] += 60
            b._save_state()
            t[0] += 1800
            b._save_state()
        finally:
            builtins.open = ro
        check("d2. the real bot: one private push per 30 min ('Bot cannot save its state', CLEAN_STORAGE)", len(pushed) == 2
              and pushed[0]["title"] == "Bot cannot save its state" and "CLEAN_STORAGE" in pushed[0]["body"], pushed)
    finally:
        L.STATE_PATH = real
    with open(b.state_path, "w") as fh:
        fh.write("{torn")
    b2 = _bot(tmp)
    try:
        b2._restore()
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = e
    check("d3. corrupt live_state.json: a clean start, never raises", ok is True, ok)


def t_corrupt_files():
    print("e. corrupt account files", flush=True)
    from engine import multi_account as MA, rapid as RP, account_b as AB
    notes = []
    FN.PUSH = notes.append
    FN._SEEN.clear()
    try:
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "accounts.json")
        check("e1. accounts.json missing -> [] and no note", MA.load_file(p) == [] and not notes)
        with open(p, "w") as fh:
            fh.write('{"accounts": [')
        check("e2. accounts.json corrupt -> [] (never armed) + one note naming it", MA.load_file(p) == [] and len(notes) == 1
              and "accounts.json" in notes[0]["title"] and "do not trade" in notes[0]["body"], notes)
        MA.load_file(p)
        check("e3. the same file again the same day: no second note", len(notes) == 1, notes)
        rp = os.path.join(tmp, "rapid.json")
        with open(rp, "w") as fh:
            fh.write("[[")
        check("e4. rapid.json corrupt -> off (read None) + a note", RP.read(rp) is None and any("rapid.json" in n["title"] for n in notes), notes)
        sm = os.path.join(tmp, "second_model.json")
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        with open(sm, "w") as fh:
            json.dump({"account_b": None}, fh)
        with open(os.path.join(tmp, "data", "account_b.json"), "w") as fh:
            fh.write("{oops")
        check("e5. account_b.json corrupt -> the old fallback (not found) + a note", AB.read_local(sm) == (False, None)
              and any("account_b.json" in n["title"] for n in notes), notes)
        check("e6. a temp file never touches logs/faults.json or the phone (only data/ files push for real)",
              not FN._real(p) and FN._real(os.path.join(FN.DATA, "accounts.json")))
    finally:
        FN.PUSH = None
        FN._SEEN.clear()


def t_lanes():
    print("f. one lane's exception", flush=True)
    tmp = tempfile.mkdtemp()
    b = _bot(tmp)

    class Boom:
        problem = None
        adapter = None

        def tick(self, *a, **k):
            raise RuntimeError("lane exploded")
        adapter_tick = tick
    b._sync_account_b = lambda: None
    b.acct_b = Boom()
    b._rapid_atlases = lambda: [Boom()]
    errs = []
    b._note_error = errs.append
    ok = True
    try:
        b._account_b_tick(None, None, "NQ", 1795000000)
        b._fleet_block = lambda: (_ for _ in ()).throw(RuntimeError("fleet exploded"))
        b._fleet_tick("NQ", 1795000000)
    except Exception as e:  # noqa: BLE001
        ok = e
    check("f1. ATLAS, a Rapid ATLAS and the fleet raising: nothing raises out of the poll, each is logged",
          ok is True and sum("exploded" in e for e in errs) == 3, (ok, errs))
    from engine import multi_account as MA
    acc = MA.Account.__new__(MA.Account)
    logs = []
    acc.log = lambda k, t: logs.append((k, t))
    acc._process = lambda ctx: (_ for _ in ()).throw(RuntimeError("extra exploded"))
    try:
        acc.process({})
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = e
    check("f2. one extra account raising: logged, the next accounts still route (process never raises)", ok is True
          and logs and "extra exploded" in logs[0][1], (ok, logs))
    src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    body = src.split("    def poll_once(self):", 1)[1].split("\n    def ", 1)[0]
    i_route, i_save = body.index("self._route_signals("), body.index("self._save_state()")
    lanes = [body.index(x) for x in ("self._account_c_tick(", "self._account_b_tick(", "self._fleet_tick(", "self._keepalive_tick(df1")]
    check("f3. LIT routes and the state is saved BEFORE any other lane runs in the poll", all(i_route < i_save < x for x in lanes))


def t_internet():
    print("g. internet down", flush=True)
    from engine import alerts as AL
    tmp = tempfile.mkdtemp()
    b = _bot(tmp)
    co, sd = AL.chat_on, AL.send
    done = threading.Event()

    def slow(text, kind="signal", force=False):
        time.sleep(1.5)
        done.set()
        return {"sent": False}
    try:
        AL.chat_on, AL.send = (lambda: True), slow
        t0 = time.time()
        r = b._alert("entry", "entry")
        dt_ = time.time() - t0
        check("g1. chat alerts on + a hung network: _alert returns at once (the post runs in a thread)", dt_ < 0.5 and r == {"queued": True}
              and done.wait(5), (dt_, r))
        AL.chat_on = lambda: False
        seen = []
        AL.send = lambda text, kind="signal", force=False: seen.append(text) or {"sent": False}
        b._alert("x", "entry")
        check("g2. chat alerts off: the old synchronous path (test harnesses see it at once)", seen == ["x"], seen)
    finally:
        AL.chat_on, AL.send = co, sd
    po = AL._post
    try:
        AL._post = lambda url, body: (_ for _ in ()).throw(OSError("network unreachable"))
        cfg_load = AL.load
        AL.load = lambda: {"telegram_token": "t", "telegram_chat": "c", "discord_webhook": "w", "events": {"entry": True}}
        AL.chat_on = lambda: True
        r = AL.send("x", "entry")
        check("g3. alerts.send with the network down: returns the errors, never raises", "error" in str(r), r)
    finally:
        AL._post, AL.load, AL.chat_on = po, cfg_load, co


def t_hist():
    print("h. the history export torn mid-session", flush=True)
    tmp = tempfile.mkdtemp()
    dd = L.DATA_DIR
    L.DATA_DIR = tmp
    try:
        b = _bot(tmp)
        b.no_yahoo = True
        b._archive = lambda sym, tf: L.pcbars.tidy(None)
        notes = []
        b._nt_note = lambda key, kind, text, every_s=900: notes.append(text)
        b.clock = lambda: 1795000400
        p = os.path.join(tmp, "NQ_5m.csv")
        with open(p, "w") as fh:
            fh.write(HDR + "".join(f"{1795000000 + 300 * i},1,2,0.5,1.5,10\n" for i in range(3)))
        a = b._read_hist("NQ", "5m")
        time.sleep(0.01)
        with open(p, "w") as fh:
            fh.write("this is not, a csv\x00\x00")
        c = b._read_hist("NQ", "5m")
        check("h1. torn after a good read: the last good copy (same bars) + one note", len(a) == 3 and c is not None and list(c["time"]) == list(a["time"])
              and notes and "last good copy" in notes[0], (len(a), None if c is None else len(c), notes))
        b2 = _bot(tmp)
        b2.no_yahoo = True
        b2._archive = b._archive
        try:
            b2._read_hist("NQ", "5m")
            ok = False
        except Exception:
            ok = True
        check("h2. no good copy yet: it raises as before (the poll fails, the fast alarm tells the owner)", ok)
    finally:
        L.DATA_DIR = dd


def main():
    t_feed()
    t_oif()
    t_adapter_state()
    t_bot_state()
    t_corrupt_files()
    t_lanes()
    t_internet()
    t_hist()
    bad = [n for n, ok in RES if not ok]
    print(f"\n{len(RES) - len(bad)}/{len(RES)} passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
