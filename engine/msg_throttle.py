"""Messaging throttle (night-risk 2026-11-18, docs/ZEUS_FEATURES.md #25): a runaway-order alarm for each NinjaTrader account.

The adapter (engine/ninjatrader.py) already caps ENTRY files at 8 a trading day per account. This counts EVERY order file the
bot writes (entries, adds, stop / target CHANGEs, CANCELs, CLOSEPOSITIONs) and trips when the bot is clearly looping:

  burst     more than PER_MIN files in 60 seconds (a normal trade is 1-4 files a minute)
  day       more than PER_DAY files in one CME trading day (8 trades x ~10 files is ~80)
  change    more than CHANGE_PER_ORDER CHANGE lines on ONE order id in a day (a stop-modify loop)

MONITOR, ON: a trip writes one "risk_alert" Board event and the adapter's critical alert (BOT._alert + phone), and the PC report
(tools/pc_report.py, key risk:throttle:...) pushes it once (type problems). Nothing is refused.
BLOCK, OFF by default (it acts on orders): when switched on, a tripped account refuses NEW entries and adds until the next CME
trading day or a reset. Stop / target changes, cancels, closes, flatten and KILL are NEVER throttled: protection always goes out.
  python -X utf8 -m engine.msg_throttle --block-on     # one line to turn the block on (--block-off; LE_MSG_THROTTLE_BLOCK=0/1 wins)
  python -X utf8 -m engine.msg_throttle --reset        # after checking: clear today's trips on every account (unblocks)
  python -X utf8 -m engine.msg_throttle                # print each account's counts and trips
State per adapter next to its state file: data/ninjatrader_state*_msgs.json (gitignored; account shown by its last 4 only).
Tests: tests/test_risk_monitors.py and `python -m engine.ninjatrader --selftest`.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
SWITCH = os.path.join(ROOT, "data", "msg_throttle.json")          # {"block": true}: written by --block-on (gitignored)
PER_MIN, PER_DAY, CHANGE_PER_ORDER = 20, 150, 12
VERSION = 1


def trading_day(t) -> str:
    """CME trading day: 18:00 ET opens the next day (the adapter's own rule)."""
    e = dt.datetime.fromtimestamp(int(t), ET)
    if e.hour >= 18:
        e += dt.timedelta(days=1)
    while e.weekday() >= 5:
        e += dt.timedelta(days=1)
    return e.date().isoformat()


def path_for(state_path: str) -> str:
    return os.path.splitext(state_path)[0] + "_msgs.json"


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write(path, obj):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"))
        os.replace(tmp, path)        # one try, no retry wait: best effort, it runs right after an order file is written
    except Exception:
        pass


def block_on(cfg: dict | None = None, env=None, switch_path: str | None = None) -> bool:
    """Is the BLOCK switched on? cfg nt_msg_throttle_block (tests) > LE_MSG_THROTTLE_BLOCK > data/msg_throttle.json. Default OFF."""
    cfg = cfg or {}
    if cfg.get("nt_msg_throttle_block") is not None:
        return bool(cfg.get("nt_msg_throttle_block"))
    env = os.environ if env is None else env
    v = str(env.get("LE_MSG_THROTTLE_BLOCK", "")).strip()
    if v in ("0", "1"):
        return v == "1"
    d = _read(switch_path or SWITCH, {})
    return bool(isinstance(d, dict) and d.get("block"))


class Throttle:
    """One per NinjaTrader adapter. note(lines, now) after every order file written -> a new trip dict or None.
    entry_block(now) -> the refusal text when the BLOCK is on and this account tripped today, else None. Never raises."""

    def __init__(self, path: str, account: str = "", cfg: dict | None = None, switch_path: str | None = None):
        cfg = cfg or {}
        self.path = path
        self.cfg = cfg
        self.switch_path = switch_path
        self.acct4 = str(account or "")[-4:]
        self.per_min = int(cfg.get("nt_msg_per_min", PER_MIN))
        self.per_day = int(cfg.get("nt_msg_per_day", PER_DAY))
        self.change_per_order = int(cfg.get("nt_change_per_order", CHANGE_PER_ORDER))
        self.on = cfg.get("nt_msg_throttle", True) is not False
        s = _read(path, {}) if self.on else {}
        s = s if isinstance(s, dict) else {}
        self.s = {"v": VERSION, "acct4": self.acct4, "day": s.get("day"), "n_day": int(s.get("n_day") or 0),
                  "recent": [int(x) for x in s.get("recent") or [] if isinstance(x, (int, float))][-200:],
                  "changes": {str(k): int(v) for k, v in (s.get("changes") or {}).items() if isinstance(v, (int, float))},
                  "trips": [x for x in s.get("trips") or [] if isinstance(x, dict)][-20:]}

    def _roll(self, now):
        day = trading_day(now)
        if self.s["day"] != day:
            self.s.update(day=day, n_day=0, changes={})
        self.s["recent"] = [t for t in self.s["recent"] if now - t < 60]

    def tripped_today(self, now=None) -> list:
        day = trading_day(now or time.time())
        return [x for x in self.s["trips"] if x.get("day") == day and not x.get("cleared")]

    def note(self, lines, now=None) -> dict | None:
        if not self.on:
            return None
        try:
            now = int(now or time.time())
            self._roll(now)
            self.s["n_day"] += 1
            self.s["recent"].append(now)
            for ln in lines or []:
                f = str(ln).split(";")
                if f[0] == "CHANGE" and len(f) > 10 and f[10]:
                    self.s["changes"][f[10]] = self.s["changes"].get(f[10], 0) + 1
            trip = None
            have = {x.get("code") for x in self.tripped_today(now)}
            if len(self.s["recent"]) > self.per_min and "burst" not in have:
                trip = ("burst", f"{len(self.s['recent'])} order files in 60 seconds (normal is 1-4)")
            elif self.s["n_day"] > self.per_day and "day" not in have:
                trip = ("day", f"{self.s['n_day']} order files this trading day (limit {self.per_day})")
            else:
                hot = [k for k, v in self.s["changes"].items() if v > self.change_per_order]
                if hot and "change" not in have:
                    trip = ("change", f"{self.s['changes'][hot[0]]} stop/target changes on one order today (limit {self.change_per_order})")
            rec = None
            if trip:
                rec = {"t": now, "day": self.s["day"], "code": trip[0], "text": trip[1], "acct4": self.acct4,
                       "block": block_on(self.cfg, switch_path=self.switch_path)}
                self.s["trips"] = (self.s["trips"] + [rec])[-20:]
            _write(self.path, self.s)
            return rec
        except Exception:
            return None

    def entry_block(self, now=None) -> str | None:
        try:
            if not self.on:
                return None
            trips = self.tripped_today(now)
            if not trips or not block_on(self.cfg, switch_path=self.switch_path):
                return None
            return (f"message throttle tripped ({trips[0]['text']}): no new entries today. Check the bot log; "
                    "python -X utf8 -m engine.msg_throttle --reset clears it")
        except Exception:
            return None


def say(rec: dict) -> tuple:
    acct = f"account ...{rec.get('acct4')}" if rec.get("acct4") else "an account"
    title = "ZEUS throttle: runaway orders?"
    body = (f"NinjaTrader {acct}: {rec.get('text')}. A bot loop looks likely. "
            + ("New entries are BLOCKED today (stops, closes and flatten still go out). " if rec.get("block") else
               "Nothing was blocked (the block is OFF). ")
            + "Check NinjaTrader Orders + the bot log; flatten from the phone /safety/ page if it looks wrong.")
    return title, body


def flags(root: str = ROOT, now=None, max_age_s: int = 2 * 86400) -> list:
    """tools/pc_report.py's hook: every trip of the last 2 days on any account -> one push each (key risk:throttle:...)."""
    out = []
    now = int(now or time.time())
    try:
        for p in sorted(glob.glob(os.path.join(root, "data", "ninjatrader_state*_msgs.json"))):
            s = _read(p, {})
            for r in (s.get("trips") if isinstance(s, dict) else None) or []:
                if not isinstance(r, dict) or now - int(r.get("t") or 0) > max_age_s:
                    continue
                title, body = say(r)
                out.append({"key": f"risk:throttle:{r.get('acct4') or 'x'}:{r.get('day')}:{r.get('code')}", "t": int(r["t"]),
                            "title": title, "body": body, "code": r.get("code")})
    except Exception:
        pass
    return out


def reset(root: str = ROOT, now=None) -> int:
    """Clear today's trips on every account (marked cleared, kept for the record). -> trips cleared."""
    n = 0
    day = trading_day(now or time.time())
    for p in glob.glob(os.path.join(root, "data", "ninjatrader_state*_msgs.json")):
        s = _read(p, {})
        if not isinstance(s, dict):
            continue
        for r in s.get("trips") or []:
            if isinstance(r, dict) and r.get("day") == day and not r.get("cleared"):
                r["cleared"] = int(now or time.time())
                n += 1
        _write(p, s)
    return n


def main(argv=None) -> int:
    import sys
    a = list(sys.argv[1:] if argv is None else argv)
    if "--block-on" in a or "--block-off" in a:
        _write(SWITCH, {"block": "--block-on" in a, "t": int(time.time())})
        print("Message throttle BLOCK is now " + ("ON: a tripped account takes no new entries until tomorrow." if "--block-on" in a
                                                  else "OFF: trips only alert.") + " The running bot reads it at the next entry.")
        return 0
    if "--reset" in a:
        print(f"Cleared {reset()} trip(s) for today.")
        return 0
    print(f"Block: {'ON' if block_on() else 'OFF'} (limits: {PER_MIN} files a minute, {PER_DAY} a day, {CHANGE_PER_ORDER} changes an order)")
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "ninjatrader_state*_msgs.json"))):
        s = _read(p, {})
        print(f"  ...{s.get('acct4')}: {s.get('n_day')} files on {s.get('day')}; trips: "
              + (", ".join(f"{r.get('code')} {r.get('day')}" + (" (cleared)" if r.get("cleared") else "") for r in s.get("trips") or []) or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
