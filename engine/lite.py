"""LITE mode (owner 2026-11-03: "run my bot very low memory"): the PC bot without its read-only add-ons and with only the
history the strategy reads. Trading decisions are unchanged (tests/test_lite.py replays LiveBot sessions with and
without LITE: the same orders, exits, $ and state).

Switch (NOT live_model*.json): data/lite.json {"on": true} (written by BOT_LITE.bat; gitignored), or the env LE_LITE=1
(LE_LITE=0 forces it off whatever the file says). Read once when server.py starts: a change needs a server restart.

What LITE turns off (all read-only: none of them decides, sizes or routes a trade):
  - the LIT backtest prewarm of the PC dashboard (LE_PREWARM=0: ~90 MB; the page builds it on first open instead)
  - Mind (LE_MIND=0, LE_MIND_RESEARCH=0: its 5-minute compute and the nightly research child process)
  - the execution audit thread (LE_EXEC_AUDIT=0; the PC watcher, its readiness push and Sunday self-test stay on)
  - Bot Brain (LiveBot._brain_tick), Trade pictures (_chart_tick: matplotlib in the background worker process) and the
    paper second strategies / ATLAS + BLITZ shadows (_second_tick: the background worker process, ~150 MB+)
  - AI watch (ai_watch.tick inside _alerts_tick); the "setup armed" pushes and the narrator stay on
An env value the owner set himself always wins over these defaults (os.environ.setdefault).

What LITE keeps: LIT, its routing, guards, account B / C / fleet routes, the routed second-strategy route, heartbeat
(the cloud monitor needs the PC's bars), the phone live feed, auto-update, autostart, the dashboard server.

History trim: the stored 5m / 1m / ES history (data/<sym>_<tf>.csv, 5 years) is cut to the last `hist_days` days (default
100) when it is read. LIT reads only from engine/lit_live.window_start (18:00 ET opening the previous month's first
trading day minus 7 days: at most ~70 days back); the second strategies use the same window. 100 days keeps a month of
margin. engine/live.py stays byte-identical (the PC's hand-patched copy must keep fast-forwarding): LITE wraps the
LiveBot instance like engine/poll_timing.py does.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LITE_PATH = os.path.join(ROOT, "data", "lite.json")
DEFAULTS = {"on": False, "hist_days": 100}
MIN_HIST_DAYS = 75                     # never fewer: LIT's window reaches ~70 days back (lit_live.window_start)
ENV_OFF = {"LE_PREWARM": "0", "LE_MIND": "0", "LE_MIND_RESEARCH": "0", "LE_EXEC_AUDIT": "0"}
OFF_STAGES = ("_brain_tick", "_chart_tick", "_second_tick")   # LiveBot methods LITE replaces with a no-op (read-only)
_HIST_TF = ("1m", "5m", "15m", "1h")


def settings(path: str | None = None, env=None) -> dict:
    """{"on", "hist_days", "why"}: data/lite.json merged on the defaults; env LE_LITE=1 / 0 overrides "on"."""
    env = os.environ if env is None else env
    out = dict(DEFAULTS)
    p = path or LITE_PATH
    try:
        with open(p, encoding="utf-8") as fh:
            got = json.load(fh)
        if isinstance(got, dict):
            out.update({k: got[k] for k in DEFAULTS if k in got})
            out["why"] = "data/lite.json"
    except (OSError, ValueError):
        pass
    v = str(env.get("LE_LITE", "")).strip().lower()
    if v in ("1", "true", "on", "yes"):
        out["on"], out["why"] = True, "LE_LITE=1"
    elif v in ("0", "false", "off", "no"):
        out["on"], out["why"] = False, "LE_LITE=0"
    out["on"] = bool(out["on"])
    try:
        out["hist_days"] = max(MIN_HIST_DAYS, int(out["hist_days"]))
    except (TypeError, ValueError):
        out["hist_days"] = DEFAULTS["hist_days"]
    return out


def enabled(path: str | None = None, env=None) -> bool:
    return settings(path, env)["on"]


def apply_env(env=None, path: str | None = None) -> dict:
    """server.py, before anything reads them: the add-on off switches, as defaults only. Returns what was set."""
    env = os.environ if env is None else env
    if not enabled(path, env):
        return {}
    done = {}
    for k, v in ENV_OFF.items():
        if k not in env:
            env[k] = v
            done[k] = v
    return done


def trim(df, now: int, days: int):
    """Rows of a bar frame from now - days on (the frame itself when it has no "time" column or nothing to cut)."""
    if df is None or not len(df) or "time" not in df.columns:
        return df
    cut = int(now) - int(days) * 86400
    if int(df["time"].min()) >= cut:
        return df
    return df[df["time"] >= cut].reset_index(drop=True)


def _alerts_lite(bot):
    """LiveBot._alerts_tick without AI watch: the setup-armed pushes and the narrator, same order, same guards."""
    from engine import live as _live

    def tick(now):
        if bot.state_path != _live.STATE_PATH:
            return
        try:
            from engine import alerts_plus
            alerts_plus.pc_setup_tick(bot, now)
        except Exception as e:
            bot._note_error(f"setup alerts failed: {e.__class__.__name__}: {e}")
        try:
            from engine import narrator
            narrator.tick(bot, now)
        except Exception as e:
            bot._note_error(f"narrator failed: {e.__class__.__name__}: {e}")
    return tick


def install(bot, cfg: dict | None = None) -> dict:
    """Wrap one LiveBot (the server's BOT, or a test harness's bot) for LITE. Idempotent. Returns the info dict
    (also bot.lite)."""
    s = {**settings(), **(cfg or {})}
    if getattr(bot, "lite", None):
        return bot.lite
    days = max(MIN_HIST_DAYS, int(s.get("hist_days") or DEFAULTS["hist_days"]))
    orig_read = bot.read_hist

    def read_hist(sym, tf):
        df = orig_read(sym, tf)
        if tf not in _HIST_TF:
            return df
        now = int(bot.clock())
        out = trim(df, now, days)
        cache = getattr(bot, "_hist_cache", None)
        if isinstance(cache, dict):                        # drop the 5-year copies LiveBot._read_hist keeps in memory
            for k, (key, frame) in list(cache.items()):
                cut = trim(frame, now, days)
                if cut is not frame:
                    cache[k] = (key, cut)
        return out
    bot.read_hist = read_hist

    def _noop(*a, **kw):
        return None
    for name in OFF_STAGES:
        setattr(bot, name, _noop)
    bot._alerts_tick = _alerts_lite(bot)
    bot.brain = None
    info = {"on": True, "hist_days": days, "off": list(OFF_STAGES) + ["ai_watch"] + sorted(ENV_OFF),
            "why": s.get("why", "install")}
    bot.lite = info
    return info


def write(on: bool, path: str | None = None, hist_days: int | None = None) -> dict:
    """BOT_LITE.bat: data/lite.json on / off (keeps hist_days)."""
    p = path or LITE_PATH
    cur = settings(p, env={})
    cur.pop("why", None)
    cur["on"] = bool(on)
    if hist_days:
        cur["hist_days"] = max(MIN_HIST_DAYS, int(hist_days))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=1)
    os.replace(tmp, p)
    return cur


if __name__ == "__main__":
    import sys
    a = (sys.argv[1:] or ["status"])[0].lower()
    if a in ("on", "off"):
        print(json.dumps(write(a == "on")))
    else:
        print(json.dumps(settings()))
