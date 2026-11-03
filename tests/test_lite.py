"""LITE mode (engine/lite.py) check: the switch, the env defaults, the history trim, and that LITE trades exactly like the
full bot.

    python -X utf8 -m tests.test_lite            # unit checks + LiveBot replay full vs LITE on 3 October sessions (~2-4 min)
    python -X utf8 -m tests.test_lite --quick    # unit checks only
    python -X utf8 -m tests.test_lite --bot-sessions=2026-10-06,2026-10-07,2026-10-08

The replay is tests/test_lit_live.bot_replay (engine/live.py LiveBot + PaperAdapter, frozen clock, bars revealed as they
close) run twice: once plain, once with engine/lite.install on the bot. Every ledger row (entries, stop moves, exits, $,
times), the final state (position, LIT model state, eval clock) and the log lines about routing must be identical, and
both runs must match the backtest. Prints the peak memory of each run (psutil, when installed).
"""
from __future__ import annotations

import collections
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from engine import lite  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{(': ' + str(detail)) if detail and not ok else ''}", flush=True)
    if not ok:
        FAILS.append(name)


def unit():
    print("unit checks", flush=True)
    d = tempfile.mkdtemp(prefix="lite_test_")
    p = os.path.join(d, "lite.json")
    check("off by default (no file, no env)", lite.enabled(p, env={}) is False)
    lite.write(True, path=p)
    check("data/lite.json on", lite.enabled(p, env={}) is True)
    check("LE_LITE=0 wins over the file", lite.enabled(p, env={"LE_LITE": "0"}) is False)
    lite.write(False, path=p)
    check("LE_LITE=1 wins over the file", lite.enabled(p, env={"LE_LITE": "1"}) is True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"on": True, "hist_days": 10}, fh)
    check("hist_days never below the LIT window floor", lite.settings(p, env={})["hist_days"] == lite.MIN_HIST_DAYS)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("{broken")
    check("an unreadable file = off", lite.enabled(p, env={}) is False)
    env = {"LE_LITE": "1", "LE_MIND": "1"}
    set_ = lite.apply_env(env=env, path=p)
    check("apply_env sets the add-on switches", env.get("LE_PREWARM") == "0" and env.get("LE_EXEC_AUDIT") == "0", env)
    check("an owner's own env value wins", env["LE_MIND"] == "1" and "LE_MIND" not in set_)
    env2 = {}
    check("apply_env does nothing when off", lite.apply_env(env=env2, path=p) == {} and env2 == {})
    check("no live_model / heartbeat / trading switch touched",
          not any(k in lite.ENV_OFF for k in ("LE_HEARTBEAT", "LE_LIVE_MODEL", "NINJATRADER_LIVE", "LE_REMOTE", "LE_NO_YAHOO")))
    df = pd.DataFrame({"time": [0, 86400 * 50, 86400 * 100, 86400 * 150], "close": [1, 2, 3, 4]})
    t = lite.trim(df, now=86400 * 150, days=100)
    check("trim keeps the last N days", list(t["time"]) == [86400 * 50, 86400 * 100, 86400 * 150], list(t["time"]))
    check("trim leaves a short frame alone", lite.trim(t, now=86400 * 150, days=100) is t)
    # the window LIT reads is inside the trim on every day of 2026 (lit_live.window_start)
    from engine import lit_live
    worst = 0
    for day in pd.date_range("2026-01-01", "2026-12-31", freq="D"):
        now = int(day.timestamp()) + 20 * 3600
        worst = max(worst, (now - lit_live.window_start(now)) / 86400)
    check(f"LIT's window reaches at most {worst:.1f} days back < floor {lite.MIN_HIST_DAYS}", worst < lite.MIN_HIST_DAYS)

    class FakeBot:
        state_path = "x"
        brain = "something"

        def __init__(self):
            self.clock = lambda: 86400 * 150
            self.read_hist = lambda sym, tf: df
            self._hist_cache = {"p": ((1, 2), df)}
    b = FakeBot()
    info = lite.install(b, {"hist_days": 100})
    check("install: read-only stages are no-ops", all(getattr(b, n)() is None for n in lite.OFF_STAGES))
    check("install: history trimmed and the 5-year cache copy dropped",
          len(b.read_hist("NQ", "5m")) == 3 and len(b._hist_cache["p"][1]) == 3)
    check("install: other timeframes untouched", len(b.read_hist("NQ", "1d")) == 4)
    check("install is idempotent", lite.install(b) is info and b.lite["on"])


def _peak_mb():
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6)
    except Exception:
        return None


def replay(sessions):
    from tests import test_lit_live as TL
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    REF = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    by_day = collections.defaultdict(list)
    for t in REF:
        by_day[t["day"]].append(t)
    runs = {}
    for mode in ("full", "lite"):
        box = {}

        def on_bot(b, mode=mode):
            if mode == "lite":
                lite.install(b, {"hist_days": lite.DEFAULTS["hist_days"]})
            box["bot"] = b
        res = TL.bot_replay(P, by_day, tuple(sessions), on_bot=on_bot)
        b = box["bot"]
        runs[mode] = {"res": res, "ledger": json.dumps(list(b.ledger), sort_keys=True, default=str),
                      "state": json.dumps(b.state, sort_keys=True, default=str),
                      "routing_log": [l["text"] for l in b.log if l.get("type") in ("trade", "risk", "order", "exit")],
                      "lite": getattr(b, "lite", None), "rss_mb": _peak_mb()}
        print(f"  {mode}: routed {res['entries_ok']}/{res['want']} entries, exits {res['exits_ok']}/{res['want']}, "
              f"extra {res['extra']}, errors {len(res['errors'])}, mean poll {res['poll_ms']} ms, RSS {runs[mode]['rss_mb']} MB",
              flush=True)
    f, l = runs["full"], runs["lite"]
    check("LITE was installed on the second run only", f["lite"] is None and l["lite"] and l["lite"]["on"])
    check("both runs match the backtest", f["res"]["ok"] and l["res"]["ok"], (f["res"]["ok"], l["res"]["ok"]))
    check("identical ledger (every entry, stop move, exit, $, time)", f["ledger"] == l["ledger"])
    check("identical final state (position, LIT state, eval clock)", f["state"] == l["state"], _first_diff(f["state"], l["state"]))
    check("identical routing log", f["routing_log"] == l["routing_log"])
    check("identical routed rows", f["res"]["rows"] == l["res"]["rows"])


def _first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"at {i}: {a[max(0, i - 80):i + 80]!r} vs {b[max(0, i - 80):i + 80]!r}"
    return "length differs" if len(a) != len(b) else ""


def main():
    unit()
    if "--quick" not in sys.argv:
        bs = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--bot-sessions=")), None)
        sessions = bs or ["2026-10-13", "2026-10-14", "2026-10-15"]
        print(f"LiveBot replay full vs LITE on {sessions}", flush=True)
        replay(sessions)
    print("OK" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(0 if not FAILS else 1)


if __name__ == "__main__":
    main()
