"""Remote control of the PC bot from the phone, free, through GitHub (docs/REMOTE_CONTROL.md).

The owner edits ONE file, control/command.json on the branch `control` of this repo, in the GitHub app or on github.com
(the phone app's Remote page builds the exact JSON and opens the editor). Which repo (2026-11-20, control_source): the one
the PC updates from. With update_source.json (the backup repo since 2026-11-14: remote "olympus" = dcondax1-wq/olympus) the
branch `control` of THAT repo, so https://github.com/dcondax1-wq/olympus/edit/control/control/command.json; without the
file (or LE_UPDATE_SOURCE=origin) origin as before. GitHub-free mode (engine/nogithub.py) only turns it off when that
would be origin (the lost account), exactly like the auto-update. The PC server (a daemon thread, like the
auto-update one; on only with LE_REMOTE=1, which scripts/run_bot.ps1 sets) fetches that branch every ~60 s with the PC's
own git credentials (the same ones the heartbeat pushes with), reads the file and runs each new command once:

  {"id": "k-1760983320-ab12", "ts": 1760983320, "cmd": "kill"}
  {"id": "...", "ts": ..., "cmd": "stop", "now": false}        "now": true = flatten first, then stop
  or several at once: {"commands": [{...}, {...}]}

  kill      = HOLD TO KILL: flatten everything (NinjaTrader FLATTENEVERYTHING), stop, auto-resume OFF, autostart cleared
  stop      stop the bot once it is flat (a position / an armed setup finishes first); "now": true flattens and stops now
  flatten   close the open position now; the bot keeps running, no new entry until the next trading day
  update    the auto-update now (engine/autoupdate.run_update: flat, outside 01:50-16:00 ET on a weekday, the update
            source only (the backup's pc branch), fast-forward only, self-tests, roll back on failure), then a restart when
            it updated
  restart   restart the server (exit 75; run_bot.ps1 starts it again) when flat, supervised, and (while the bot runs)
            outside 01:50-16:00 ET on a weekday; the auto-resume brings an opted-in eval back
  status    push a fresh heartbeat now + a phone notice with the bot's status
  start     Sim / paper ONLY: {"cmd": "start", "account": "Sim101"}. A real account is always refused (MFFU: live trading
            only with the owner present). The start body is built here from scratch: no other field of the command is used.
  pause     {"cmd": "pause", "until": "HH:MM" | "tomorrow" | "YYYY-MM-DD"}: no NEW entries until then (engine/entry_pause.py,
            checked in engine/guards.entry_problems); an open trade keeps its stop / target. Only ever blocks.
  resume_entries   lift the pause (it does not undo a remote flatten's "no new entry today", nor start a stopped bot)
  present   "I'm at the desk" check-in from the phone ({"hours": N} optional, default 4): one line in data/presence.jsonl
            (engine/presence.py). With the optional presence_required guard (OFF) it lets entries through again.
kill / stop / flatten / pause are also logged for the weekly hands-off score (engine/handsoff.py).

Never accepted: a start on a real account, any change of config / strategy / sizing / switches (no such command exists).

Rules: each command needs a unique `id` (1-64 of A-Z a-z 0-9 . _ : -) and a `ts` (unix seconds, ms, or an ISO time);
anything older than 15 min (or > 5 min in the future: a wrong clock) is ignored, and every id is handled once: done ids
are kept in data/remote_done.json (gitignored), written BEFORE the command runs (a restart never runs it twice).
Every command gets a phone notice with its result (engine/push.py pc notices) and the heartbeat line
"remote: last cmd X done at HH:MM ET" (hb_field, engine/heartbeat.py "remote").

Security: anyone with write access to the repo can write the file. kill / stop / flatten / status only reduce risk or
read; update and restart are gated to flat + the auto-update checks; nothing here can open a trade on a real account.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "control"
CMD_FILE = "control/command.json"
LOCAL_REF = "refs/le/control"                      # a private ref: never touches FETCH_HEAD, the index or the work tree
DONE_PATH = os.path.join(ROOT, "data", "remote_done.json")     # gitignored
MAX_AGE_S = 15 * 60
FUTURE_S = 5 * 60
EVERY_S = 60.0
KEEP_IDS = 300
MAX_FILE = 16 * 1024
COMMANDS = ("kill", "stop", "flatten", "update", "restart", "status", "start", "pause", "resume_entries", "present")
HANDSOFF_CMDS = ("kill", "stop", "flatten", "pause")
ID_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")


def control_source(cwd: str = ROOT, env=None, remote: str = "origin") -> dict:
    """Where the control branch is fetched from: {"remote", "url", "label"}. The default "origin" follows the update source
    (engine/autoupdate.source: update_source.json names the backup repo, remote "olympus"), so the phone's command reaches
    the PC through the repo it really updates from; origin is the lost account since 2026-11-14. Without the file, or with
    LE_UPDATE_SOURCE=origin: origin. Any other remote passed in is used as given. url: the fallback when that remote is not
    in the PC's git config yet (None for origin). Never raises."""
    if remote and remote != "origin":
        return {"remote": remote, "url": None, "label": f"{remote} ({BRANCH})"}
    try:
        from .autoupdate import _repo_words, source
        s = source(cwd, env)
        if s.get("remote") and s["remote"] != "origin":
            return {"remote": s["remote"], "url": s.get("url") or None, "label": f"{_repo_words(s.get('url'))} ({BRANCH})"}
    except Exception:
        pass
    return {"remote": "origin", "url": None, "label": f"origin ({BRANCH})"}


def enabled(env=None, root: str = ROOT) -> bool:
    env = os.environ if env is None else env
    try:
        from . import nogithub
        # GitHub-free mode (engine/nogithub.py) blocks origin only (the lost account); the backup repo still carries commands
        if nogithub.active(env, root) and control_source(root, env)["remote"] == "origin":
            return False
    except Exception:
        pass
    return env.get("LE_REMOTE", "0") == "1"


def _hm(t) -> str:
    return dt.datetime.fromtimestamp(float(t), ET).strftime("%H:%M")


# ---------------------------------------------------------------------- reading the command file
def fetch(cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH, timeout=60, url: str | None = None) -> dict:
    """git fetch the control branch into LOCAL_REF and read control/command.json. {"ok", "text" | "error", "commit"}.
    url (control_source): used instead when `remote` is not in this checkout's git config (a PC not connected yet)."""
    try:
        # (2026-11-03) the network step goes through heartbeat.run_cmd: on Windows subprocess.run(timeout=) waits without a
        # limit for its pipes while git-remote-https / the credential manager hang, which would stall this thread and with
        # it every phone command (kill included). run_cmd uses temp files, kills the whole tree at the timeout, never prompts.
        from .heartbeat import _NET_CFG, _git_env, run_cmd

        def _go(where):
            return run_cmd(["git", *_NET_CFG, "fetch", "-q", "--no-tags", where, f"+refs/heads/{branch}:{LOCAL_REF}"], cwd=cwd,
                           timeout=timeout, env=_git_env())
        r = _go(remote)
        if r.returncode and url and "does not appear to be a git repository" in (r.err or "").lower():
            r = _go(url)
        if r.returncode:
            err = r.err
            return {"ok": False, "error": f"no control branch yet on {remote} (python tools/init_control_branch.py makes it)"
                    if "couldn't find remote ref" in err.lower() else (err[-200:] or "git fetch failed")}
        c = subprocess.run(["git", "rev-parse", LOCAL_REF], cwd=cwd, capture_output=True, text=True, timeout=30)
        s = subprocess.run(["git", "show", f"{LOCAL_REF}:{CMD_FILE}"], cwd=cwd, capture_output=True, timeout=30)
        if s.returncode:
            return {"ok": False, "error": f"no {CMD_FILE} on the control branch", "commit": c.stdout.strip()[:10]}
        if len(s.stdout) > MAX_FILE:
            return {"ok": False, "error": f"{CMD_FILE} is larger than {MAX_FILE // 1024} KB: ignored"}
        return {"ok": True, "text": s.stdout.decode("utf-8", errors="replace"), "commit": c.stdout.strip()[:10]}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def parse(text: str) -> list:
    """The command objects of the file: one object, or {"commands": [...]}. Bad JSON -> []."""
    try:
        d = json.loads(text or "")
    except Exception:
        return []
    if isinstance(d, dict) and isinstance(d.get("commands"), list):
        return [c for c in d["commands"] if isinstance(c, dict)][:20]
    return [d] if isinstance(d, dict) else []


def parse_ts(v):
    """Unix seconds, unix ms or an ISO time (Z / offset; no offset = UTC) -> seconds, else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return x / 1000.0 if x > 1e12 else x
    if isinstance(v, str) and v.strip():
        s = v.strip()
        if re.fullmatch(r"\d+(\.\d+)?", s):
            return parse_ts(float(s))
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return d.timestamp()
        except ValueError:
            return None
    return None


def screen(c: dict, now: float, done: dict) -> str | None:
    """None when the command may run, else why it is ignored: 'blank' (the template: silent), 'duplicate' (silent),
    or a reason the owner is told about."""
    cid = c.get("id")
    cmd = str(c.get("cmd") or "").strip().lower()
    if not cid and cmd in ("", "none"):
        return "blank"
    if cmd in ("", "none"):
        return "blank"
    if not isinstance(cid, str) or not ID_RE.match(cid):
        return "bad id (1-64 letters, digits . _ : -)"
    if cid in done:
        return "duplicate"
    if cmd not in COMMANDS:
        return f"unknown command {cmd[:20]!r} (allowed: {', '.join(COMMANDS)}); config / strategy changes are never accepted"
    ts = parse_ts(c.get("ts"))
    if ts is None:
        return "no valid ts"
    if now - ts > MAX_AGE_S:
        return f"too old (sent {int((now - ts) // 60)} min ago; commands expire after {MAX_AGE_S // 60} min)"
    if ts - now > FUTURE_S:
        return "ts is in the future (check the phone's clock)"
    return None


# ---------------------------------------------------------------------- done ids (data/remote_done.json)
def load_done(path: str = DONE_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_done(d: dict, path: str = DONE_PATH):
    ids = d.get("done") or {}
    if len(ids) > KEEP_IDS:                         # keep the newest KEEP_IDS
        d["done"] = dict(sorted(ids.items(), key=lambda kv: float((kv[1] or {}).get("t") or 0))[-KEEP_IDS:])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)


def hb_field(path: str | None = None, env=None, now=None) -> dict:
    """The heartbeat's "remote" block: {"on", "last": "remote: last cmd kill done at 14:02 ET", "pending_stop", "error"}."""
    d = load_done(path or DONE_PATH)
    last = d.get("last") or {}
    line = None
    if last.get("cmd"):
        line = f"remote: last cmd {last['cmd']} {last.get('status') or 'done'} at {_hm(last.get('t') or 0)} ET"
    out = {"on": enabled(env), "via": control_source(ROOT, env)["label"], "last": line, "status": last.get("status"), "t": last.get("t"),
           "pending_stop": bool(d.get("pending_stop")), "error": (d.get("fetch") or {}).get("error")}
    out.update(_extras(os.path.dirname(path or DONE_PATH), now))
    return out


def _extras(folder: str, now=None) -> dict:
    """The pause, presence and hands-off blocks that ride with "remote" to the cloud and the phone's live.json (small).
    Never raises."""
    out = {}
    try:
        from . import entry_pause
        p = entry_pause.active(now, path=os.path.join(folder, entry_pause.NAME))
        out["pause"] = {"until": p["until"], "label": p.get("label"), "src": p.get("src")} if p else None
    except Exception:
        pass
    try:
        from . import presence, guards
        cfg = guards.config(None)
        out["presence"] = presence.compact(path=os.path.join(folder, "presence.jsonl"), cfg=cfg)
    except Exception:
        pass
    try:
        from . import handsoff
        out["handsoff"] = handsoff.compact(path=os.path.join(folder, "handsoff.jsonl"),
                                           presence_path=os.path.join(folder, "presence.jsonl"))
    except Exception:
        pass
    try:                                         # manual steps this week (engine/autopilot.py, docs/AUTOPILOT.md)
        from . import autopilot
        out["autopilot"] = autopilot.compact(folder, now)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------- the controller
def default_notify(title: str, body: str, key: str):
    """Phone push (kind 'pc', always pushed: engine/autoupdate.notify) + the bot's chat alert."""
    try:
        from . import autoupdate
        autoupdate.notify(title, body, key=key)
    except Exception:
        pass


def bot_status_text(bot) -> str:
    """One-line status for the phone: running, adapter / account, position, kill, LIT stage, version."""
    st = getattr(bot, "state", None) or {}
    cfg = getattr(bot, "cfg", None) or {}
    parts = ["RUNNING" if getattr(bot, "running", False) else "STOPPED"]
    if cfg:
        acct = getattr(getattr(bot, "adapter", None), "account", None) or cfg.get("nt_account")
        parts.append(f"{cfg.get('adapter', 'paper')}{(' ' + str(acct)) if acct else ''}")
    pos = st.get("position")
    parts.append(f"{'LONG' if pos.get('dir') == 1 else 'SHORT'} {pos.get('qty')} open" if isinstance(pos, dict) and pos else "flat")
    if getattr(bot, "kill", False):
        parts.append("KILL flag on")
    try:
        from .accounts import _lit_stage
        stg = _lit_stage(st).get("stage")
        if stg:
            parts.append(f"LIT stage {stg}")
    except Exception:
        pass
    h = getattr(bot, "health", None) or {}
    if h.get("data_age_s") is not None:
        parts.append(f"feed age {int(h['data_age_s'])} s")
    if h.get("entries_blocked"):
        parts.append("entries blocked (feed stale)")
    try:
        from .autoupdate import version
        v = version().get("sha")
        if v:
            parts.append(f"version {v}")
    except Exception:
        pass
    return " · ".join(parts)


class RemoteControl:
    """Daemon thread in server.py. hooks (server.py fills them; tests pass fakes):
      kill()      -> dict   the HOLD TO KILL path (auto-resume off, BOT.kill_switch, autostart cleared)
      stop()      -> dict   POST /api/live/stop (BOT.stop + autostart cleared)
      flatten()   -> dict   BOT.flatten_now
      start(body) -> dict   the start hook (BOT.start + autostart record); remote = Sim / paper only
      beat()      -> dict   one heartbeat push now
      exit(code)            leave the server with that code (75: run_bot.ps1 restarts it)
      update()    -> dict   engine/autoupdate run_update + record (optional: the default runs the real one)
    """

    def __init__(self, bot, hooks: dict | None = None, cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH,
                 done_path: str = DONE_PATH, clock=time.time, notify=None, log=print, every_s: float = EVERY_S, env=None):
        self.bot, self.hooks, self.cwd, self.remote, self.branch = bot, dict(hooks or {}), cwd, remote, branch
        self.done_path, self.clock, self.notify, self.log, self.every_s = done_path, clock, notify or default_notify, log, every_s
        self.env = env
        folder = os.path.dirname(done_path)            # data/ on the PC: presence.jsonl, handsoff.jsonl
        self.presence_path = os.path.join(folder, "presence.jsonl")
        sp = getattr(bot, "state_path", None)
        from . import entry_pause, handsoff
        self.pause_path = entry_pause.path_for(bot) if sp else os.path.join(folder, entry_pause.NAME)
        self.handsoff_path = handsoff.path_for(bot) if sp else os.path.join(folder, "handsoff.jsonl")
        self._stop = threading.Event()
        self._thread = None
        self._err_at = 0.0
        self.busy = False

    # ---- helpers
    def _env(self):
        return os.environ if self.env is None else self.env

    def _flat(self) -> str | None:
        from .autoupdate import bot_flat_reason
        return bot_flat_reason(self.bot)

    def _hook(self, name, *a):
        fn = self.hooks.get(name)
        if not callable(fn):
            return {"ok": False, "error": f"no {name} hook"}
        try:
            return dict(fn(*a) or {"ok": True})
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    def _finish(self, d: dict, cid: str, cmd: str, status: str, msg: str, now: float, title: str | None = None):
        rec = {"cmd": cmd, "t": int(now), "status": status, "msg": str(msg)[:300]}
        d.setdefault("done", {})[cid] = rec
        d["last"] = {"id": cid, **rec}
        save_done(d, self.done_path)
        self.log(f"[remote] {cmd} ({cid}): {status}: {msg}")
        if cmd in HANDSOFF_CMDS and status == "done" and not re.search(r"already stopped|never started", str(msg)):
            from . import handsoff
            handsoff.record(cmd, "phone", str(msg)[:160], now=now, path=self.handsoff_path)
        self.notify(title or f"Remote {cmd}: {status}", str(msg)[:500], f"remote:{cid}:{status}")

    # ---- the commands
    def run_cmd(self, c: dict, d: dict, now: float) -> tuple:
        """(status, message). status: done | refused | failed | pending."""
        cmd = str(c.get("cmd")).strip().lower()
        bot = self.bot
        if cmd == "kill":
            r = self._hook("kill")
            return ("done", "KILL: flattened everything, bot stopped, auto-resume OFF. Start it again at the PC.") if r.get("ok") \
                else ("failed", f"kill NOT confirmed ({r.get('error')}): flatten in NinjaTrader / the MFFU app NOW")
        if cmd == "flatten":
            if not (getattr(bot, "cfg", None) or {}):
                return "done", "the bot was never started: nothing to flatten"
            r = self._hook("flatten")
            if not r.get("ok"):
                return "failed", f"flatten NOT confirmed ({r.get('error') or (r.get('result') or {}).get('error')}): check NinjaTrader"
            return "done", ("position closed" if r.get("had_position") else "no open position") + \
                "; the bot keeps running, no new entry until the next trading day"
        if cmd == "stop":
            if not getattr(bot, "running", False):
                self._hook("stop")                   # clears a left-over autostart record too
                return "done", "the bot was already stopped"
            if c.get("now") is True:
                fr = self._hook("flatten")
                r = self._hook("stop")
                ok = fr.get("ok") and r.get("ok")
                return ("done" if ok else "failed"), ("flattened and stopped" if ok else
                                                      f"flatten {fr.get('ok')} / stop {r.get('ok')}: check NinjaTrader")
            why = self._flat()
            if why:
                d["pending_stop"] = {"id": c.get("id"), "t": int(now)}
                return "pending", f"will stop once flat ({why})"
            r = self._hook("stop")
            return ("done", "bot stopped (it was flat)") if r.get("ok") else ("failed", f"stop failed: {r.get('error')}")
        if cmd == "status":
            return "done", bot_status_text(bot)          # the fresh heartbeat goes out right after (tick)
        if cmd == "start":
            return self._start(c)
        if cmd in ("pause", "resume_entries", "present"):
            return self._owner(cmd, c, now)
        if cmd in ("update", "restart"):
            return self._gated(cmd, now)
        return "refused", "unknown command"

    def _start(self, c: dict) -> tuple:
        from .ninjatrader import is_sim
        acct = str(c.get("account") or "Sim101").strip()
        if getattr(self.bot, "running", False):
            return "refused", "the bot is already running"
        if acct.lower() == "paper":
            body = {"sym": "NQ", "tf": "5m", "adapter": "paper", "poll_sec": 60, "data_source": "ninjatrader"}
        elif is_sim(acct):
            body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "poll_sec": 60,
                    "data_source": "ninjatrader", "nt_account": acct}
            folder = (getattr(self.bot, "cfg", None) or {}).get("nt_folder")
            if folder:
                body["nt_folder"] = folder
        else:
            return "refused", (f"{acct[:40]} is a REAL account: a remote start is never allowed (MFFU: live trading only with "
                               "you at the PC). Remote start works on Sim accounts only.")
        r = self._hook("start", body)
        return ("done", f"started on {acct}") if r.get("ok") else ("failed", f"start failed: {r.get('error')}")

    def _owner(self, cmd: str, c: dict, now: float) -> tuple:
        """pause / resume_entries / present: files only (engine/entry_pause.py, engine/presence.py); no order is sent."""
        from . import entry_pause, presence
        if cmd == "pause":
            r = entry_pause.set_pause(c.get("until"), now, self.pause_path, src="phone", cid=str(c.get("id")))
            if not r.get("ok"):
                return "refused", f"pause not set: {r.get('error')}"
            open_ = isinstance((getattr(self.bot, "state", None) or {}).get("position"), dict)
            return "done", (f"no new entries until {r['label']}" + ("; the open trade keeps its stop and target" if open_ else "")
                            + ". Send resume_entries to lift it.")
        if cmd == "resume_entries":
            was = entry_pause.clear(self.pause_path, now)
            extra = ""
            if getattr(self.bot, "_no_entries_day", None):
                extra = " (a remote flatten earlier today still holds new entries until the next trading day)"
            if not getattr(self.bot, "running", False):
                extra += " The bot is stopped: start it at the PC."
            return "done", ("pause lifted: new entries allowed again" if was else "no pause was running") + extra
        row = presence.check_in("phone", c.get("hours"), now, self.presence_path)
        return "done", f"checked in from the phone: present until {presence._hm(row['t'] + int(row['hours'] * 3600))} ET"

    def _gated(self, cmd: str, now: float) -> tuple:
        from . import autoupdate as au
        env = self._env()
        if env.get("LE_SUPERVISED") != "1":
            return "refused", "this server is not run by scripts\\run_bot.ps1, so it would not come back after a restart"
        why = self._flat()
        if why:
            return "refused", f"not flat ({why}): send it again after the trade / setup"
        if cmd == "restart":
            if getattr(self.bot, "running", False) and au.in_blackout(now):
                return "refused", "trading hours (no restart 01:50-16:00 ET on a weekday while the bot runs)"
            return "restart", "server restarting: back in ~10 s (Sim resumes by itself; the eval only with auto-resume on)"
        w = au.window_reason(now, "manual")
        if w:
            return "refused", w
        fn = self.hooks.get("update")
        try:
            res = fn() if callable(fn) else self._real_update(now)
        except Exception as e:
            return "failed", f"update error: {e.__class__.__name__}: {e}"
        st = res.get("status")
        if res.get("restart"):
            return "restart", f"updated {str(res.get('old') or '')[:7]} -> {str(res.get('new') or '')[:7]}, self-tests passed: restarting"
        return ("done" if st in ("up_to_date",) else "refused" if st in ("skipped", "off") else "failed"), \
            f"update {st}: {res.get('reason')}"

    def _real_update(self, now):
        from . import autoupdate as au
        state = au.load_state()
        sh = au.Shell(log=au.file_log)
        au.file_log("remote update (owner, control branch)")
        # the owner asked for it: the opt-in toggle is not needed, every other rule stays (LE_AUTOUPDATE=0 still blocks it)
        res = au.run_update(sh, "manual", now, None, state={**state, "enabled": True})
        au.record(res)
        return res

    # ---- one pass
    def pending_tick(self, now=None):
        """A 'stop after flat' waits here: stop as soon as the bot is flat (or already stopped)."""
        now = self.clock() if now is None else now
        d = load_done(self.done_path)
        p = d.get("pending_stop")
        if not p:
            return None
        if getattr(self.bot, "running", False) and self._flat():
            return None
        d.pop("pending_stop", None)
        r = self._hook("stop")
        cid = str(p.get("id") or "stop")
        self._finish(d, cid, "stop", "done" if r.get("ok") else "failed",
                     "bot stopped (now flat)" if r.get("ok") else f"stop failed: {r.get('error')}", now)
        return r

    def tick(self, now=None) -> list:
        """Fetch, then run each new command once. Returns [(id, cmd, status, msg)]."""
        now = self.clock() if now is None else now
        out = []
        if self.busy:
            return out
        self.busy = True
        try:
            self.pending_tick(now)
            src = control_source(self.cwd, self._env(), self.remote)     # the backup repo when update_source.json names it
            f = fetch(self.cwd, src["remote"], self.branch, url=src["url"])
            d = load_done(self.done_path)
            if not f["ok"]:
                if (d.get("fetch") or {}).get("error") != f["error"]:
                    d["fetch"] = {"error": f["error"], "t": int(now)}
                    save_done(d, self.done_path)
                if time.time() - self._err_at > 3600:
                    self._err_at = time.time()
                    self.log(f"[remote] {f['error']}")
                return out
            if d.get("fetch"):
                d.pop("fetch", None)
                save_done(d, self.done_path)
            for c in parse(f["text"]):
                d = load_done(self.done_path)
                done = d.get("done") or {}
                why = screen(c, now, done)
                cid, cmd = c.get("id"), str(c.get("cmd") or "").strip().lower()
                if why in ("blank", "duplicate"):
                    continue
                if why:
                    if isinstance(cid, str) and ID_RE.match(cid):
                        self._finish(d, cid, cmd or "?", "ignored", why, now, title=f"Remote {cmd or 'command'} ignored")
                    out.append((cid, cmd, "ignored", why))
                    continue
                # marked BEFORE it runs: a crash or the restart itself never runs it twice
                d.setdefault("done", {})[cid] = {"cmd": cmd, "t": int(now), "status": "running", "msg": ""}
                save_done(d, self.done_path)
                status, msg = self.run_cmd(c, d, now)
                if status == "restart":
                    self._finish(d, cid, cmd, "done", msg, now)
                    try:
                        self.bot._save_state()
                    except Exception:
                        pass
                    out.append((cid, cmd, "done", msg))
                    self._hook("beat")
                    time.sleep(0 if self.hooks.get("exit") else 2)
                    fn = self.hooks.get("exit") or (lambda code: os._exit(code))
                    from .autoupdate import RESTART_CODE
                    fn(RESTART_CODE)
                    return out
                self._finish(d, cid, cmd, status, msg, now)
                out.append((cid, cmd, status, msg))
            if out:
                self._hook("beat")                   # a fresh heartbeat now: its "remote" line shows the result
            return out
        finally:
            self.busy = False

    # ---- thread
    def _run(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:
                try:                                 # a failing log (closed console) must not end the remote thread
                    self.log(f"[remote] error: {e.__class__.__name__}: {e}")
                except Exception:
                    pass
            self._stop.wait(self.every_s)

    def start(self) -> bool:
        if not enabled(self._env(), self.cwd):
            self.log("[remote] off (scripts/run_bot.ps1 sets LE_REMOTE=1)")
            return False
        self.log(f"[remote] on: reads control/command.json from {control_source(self.cwd, self._env(), self.remote)['label']} "
                 f"every ~{int(self.every_s)} s")
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="remote", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def status(self) -> dict:
        return {**hb_field(self.done_path, self._env(), self.clock()), "thread_alive": bool(self._thread and self._thread.is_alive())}
