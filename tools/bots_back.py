"""BOTS BACK helpers (scripts/bots_back.ps1 calls these; owner 2026-11-12: "we need to get these bots running again").

  python tools/bots_back.py --server-up            exit 0 when the bot server answers on 127.0.0.1:8766, else 1
  python tools/bots_back.py --wait-server 120      wait up to N seconds for it (exit 0 / 1)
  python tools/bots_back.py --wait-feed 300        NinjaTrader's LE_BarFeed bars fresh? waits up to N seconds while the market is
                                                   open (exit 0 fresh or market closed, 1 still stale)
  python tools/bots_back.py --resume-paper         the bot server up but the bot stopped: start it again with YOUR last saved start
                                                   (data/autostart.json, written by the server at every start) ONLY when that start
                                                   was paper or a NinjaTrader Sim account. A real account is never started here: that
                                                   stays START_BOT.bat, where you type the live phrase yourself.
Read-only use of the engine (engine/watchdog.mode_of / load, engine/go.feed_problem / market_open). Never places an order, never
arms, never changes live_model*.json or engine/. Tests: tests/test_bots_back.py (fake http).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PORT = int(os.environ.get("PORT") or 8766)
AUTOSTART = os.path.join(ROOT, "data", "autostart.json")
SAFE_MODES = ("paper", "demo")          # engine/watchdog.AUTO_MODES: paper, and NinjaTrader Sim / Tradovate demo


def say(tag, text):
    print(f"  [{tag}] {text}", flush=True)


def http_json(method, path, body=None, port=PORT, timeout=5):
    """-> (status, dict). Never raises. Only 127.0.0.1 (the bot server on this PC)."""
    url = f"http://127.0.0.1:{port}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8") or "{}"
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": e.__class__.__name__}


HTTP = http_json            # tests replace this


def server_up(port=PORT) -> bool:
    st, d = HTTP("GET", "/api/health/ping", port=port, timeout=3)
    return st == 200 and bool(d.get("ok"))


def bot_running(port=PORT) -> bool | None:
    st, d = HTTP("GET", "/api/live/state", port=port)
    if st != 200:
        return None
    return bool(d.get("running"))


def wait_server(seconds, port=PORT, sleep=time.sleep) -> bool:
    t0 = time.time()
    while True:
        if server_up(port):
            return True
        if time.time() - t0 >= seconds:
            return False
        sleep(3)


def safe_mode(cfg) -> str | None:
    """'paper' | 'demo' (Sim) | 'live' | None. Conservative: Tradovate counts as live, an unreadable record as live, and a
    NinjaTrader start without its own account name too (the server would take the account from .env.local.ps1, which this
    process does not see: it could be the real eval)."""
    if not isinstance(cfg, dict):
        return "live"
    if cfg.get("adapter") == "ninjatrader" and not str(cfg.get("nt_account") or "").strip():
        return "live"
    try:
        from engine import watchdog
        return watchdog.mode_of(cfg, "live")
    except Exception:
        return "live"


def load_autostart(path=None) -> dict | None:
    try:
        with open(path or AUTOSTART, encoding="utf-8") as fh:
            r = json.load(fh)
        return r if isinstance(r, dict) else None
    except Exception:
        return None


def resume_paper(port=PORT, path=None, wait_s=20, sleep=time.sleep) -> int:
    """0 running (already, or started now), 2 server down, 3 nothing safe to start, 1 the start failed."""
    if not server_up(port):
        say("FIX", "the bot server is not answering, so the bot cannot be started")
        return 2
    t0 = time.time()
    while True:                                  # the server resumes a paper / Sim bot by itself right after it starts
        r = bot_running(port)
        if r:
            say("OK", "the bot is running")
            return 0
        if time.time() - t0 >= wait_s:
            break
        sleep(2)
    rec = load_autostart(path)
    cfg = rec.get("cfg") if isinstance(rec, dict) else None
    if not isinstance(cfg, dict):
        say("SKIP", "the bot is stopped and has no saved start (the last stop was on purpose). To start it: START_BOT.bat")
        return 3
    mode = safe_mode(cfg)
    if mode not in SAFE_MODES:
        say("SKIP", "the bot is stopped; its last start was on a REAL account. BOTS_BACK never arms a real account: "
                    "START_BOT.bat, where you type the phrase yourself")
        return 3
    st, d = HTTP("POST", "/api/live/start", body=cfg, port=port, timeout=60)
    if st == 200 and d.get("ok"):
        say("OK", f"the bot started again with your last {'paper' if mode == 'paper' else 'Sim'} start "
                  f"({cfg.get('sym', 'NQ')} {cfg.get('tf', '5m')}, {cfg.get('adapter', 'paper')})")
        return 0
    say("FIX", f"the bot did not start: {str(d.get('error') or st)[:160]}")
    return 1


def wait_feed(seconds, problem=None, is_open=None, sleep=time.sleep) -> int:
    """0 fresh (or the market is closed), 1 still stale after `seconds`."""
    try:
        from engine import go
        problem = problem or go.feed_problem
        is_open = is_open or go.market_open
    except Exception as e:
        say("..", f"could not check the bars here ({e.__class__.__name__})")
        return 0
    try:
        mo = bool(is_open())
    except Exception:
        mo = True
    why = problem()
    if why is None:
        say("OK", "NinjaTrader LE_BarFeed bars are fresh")
        return 0
    if not mo:
        say("..", "market closed: NinjaTrader bars start again at the open (Sunday 18:00 ET / daily 18:00 ET)")
        return 0
    say("..", f"NinjaTrader gives no fresh bars yet ({str(why)[:120]})")
    try:
        from engine.ninjatrader import nt_instrument
        inst = nt_instrument("MNQ")
    except Exception:
        inst = "MNQ"
    say("..", f"In NinjaTrader: log in, open the {inst} chart on 5 Minute, right-click > Indicators > LE_BarFeed > Add > OK.")
    say("..", f"This window waits up to {int(seconds) // 60} minutes and goes on by itself.")
    t0 = time.time()
    while time.time() - t0 < seconds:
        sleep(15)
        if problem() is None:
            say("OK", "NinjaTrader LE_BarFeed bars are fresh")
            return 0
    say("FIX", "still no fresh NinjaTrader bars: the bot will not open new trades until they come (FEED STALE)")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BOTS BACK helpers (scripts/bots_back.ps1).")
    ap.add_argument("--port", type=int, default=PORT)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--server-up", action="store_true")
    g.add_argument("--wait-server", type=int, metavar="SECONDS")
    g.add_argument("--wait-feed", type=int, metavar="SECONDS")
    g.add_argument("--resume-paper", action="store_true")
    a = ap.parse_args(argv)
    if a.server_up:
        return 0 if server_up(a.port) else 1
    if a.wait_server is not None:
        ok = wait_server(a.wait_server, a.port)
        say("OK" if ok else "FIX", "the bot server answers" if ok else
            f"the bot server did not answer in {a.wait_server} s (its log: logs\\server-YYYYMMDD.log)")
        return 0 if ok else 1
    if a.wait_feed is not None:
        return wait_feed(a.wait_feed)
    return resume_paper(a.port)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        say("..", f"check skipped ({e.__class__.__name__}: {str(e)[:120]})")
        sys.exit(0)
