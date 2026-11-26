"""Setup progress pushes (day-closer 2026-11-25, owner: "I want those notifications too, any time we get closer").

READ-ONLY: it reads what the bot already computes (the LIT Bot Brain bot.brain, engine/brain.py: stage {key, n, label, waiting,
dir} and today's setups; the ATLAS paper twin bot.second, engine/second.py: each member's state {stage, text}, brain levels /
plan) and sends phone lines. It never starts, stops, arms, routes, sizes or changes an order. Driven by engine/watchdog (every
30 s, the real server only), never from the trading loop.

  LIT (Zlarior)   one line the first time today's setup reaches step 5, 7 and 8 of the Brain's 10 (5 = 5m CISD, the setup;
                  6 = limit armed; 7 = the limit was tapped, waiting for the 1m CISD; 8 = entering now; 9 = in the trade (its own
                  entry push), 10 = done). A jump (4 -> 7) sends one line, at the step reached. "Setup cancelled: <why>" when a
                  setup that got a line ends without a fill (the Brain's rejected / no fill / blocked text).
  ATLAS           S/R levels: price within 30 pts and within 10 pts of a level it watches (the levels the member's brain lists,
                  not taken / used); any member: the moment it ARMS (state "armed", its own words). EMA / MACD have no level
                  price in their brain, so for them the "armed" line is the alert.
  Followers       each line says which other accounts would take it too (the extra accounts on LIT, the ATLAS accounts whose
                  members include it) and which would not (not armed / start problem).
Rules: one push per setup id + step (kept across restarts in logs/setup_progress.json, today only); at most DAY_MAX (12) an ET day
(the entering line always goes); quiet 23:00-07:00 ET: only the "entering now" line is sent there (the rest are marked seen); only
for a bot on a broker account (never paper), weekdays with CME open; notify_settings.json alerts.setup_progress (default ON) or
LE_SETUP_PROGRESS=0 = off. Delivery: engine/alert_bus.send_critical (Telegram / Discord first once ALERTS_SETUP is on, else the
private ntfy topic + the Olympus app), notify type "setup_progress".
Tests: python -X utf8 -m tests.test_setup_progress
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
STATE_PATH = os.path.join(ROOT, "logs", "setup_progress.json")      # gitignored
TYPE = "setup_progress"
LIT_STEPS = (5, 7, 8)                 # the Brain's step numbers (engine/brain.STAGES)
ENTRY_STEP = 8                        # "Entering now": always sent (quiet hours, the day cap)
NEAR_PTS = (30.0, 10.0)
DAY_MAX = 12
ATLAS_MAX = 8                         # red team 2026-11-25: ATLAS lines stop at 8 a day, so a choppy ATLAS day never uses the LIT lines' room
QUIET = (23 * 60, 7 * 60)
DEAD = ("rejected", "no_fill", "blocked")


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    if str(e.get("LE_SETUP_PROGRESS", "1")).strip() == "0":
        return False
    try:
        from . import notify
        return bool(notify.on(TYPE))
    except Exception:
        return True


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


def _day(t) -> str:
    return _et(t).date().isoformat()


def _quiet(now) -> bool:
    e = _et(now)
    m = e.hour * 60 + e.minute
    a, b = QUIET
    return m >= a or m < b


def _px(v) -> str:
    try:
        return f"{float(v):,.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "?"


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _side(d) -> str:
    return "LONG" if d in (1, "long", "LONG") else "SHORT" if d in (-1, "short", "SHORT") else ""


def _live_bot(bot) -> bool:
    return bool(getattr(bot, "running", False)) and str(((getattr(bot, "cfg", None) or {}).get("adapter")) or "paper") != "paper"


def _open_hours(now) -> bool:
    if _et(now).weekday() >= 5:
        return False
    try:
        from .live import market_open
        return bool(market_open(now))
    except Exception:
        return True


def followers(bot, model: str, key: str | None = None) -> str:
    """'Also: Zlarior 25K #2, Rapid EOD 25K' / '... (not: Rapid EOD 25K - not armed)' for a line. Never raises."""
    try:
        from . import live_guard as LG
        accts = LG.lit_followers(bot) if model == "lit" else [
            a for a in LG.atlas_accounts(bot) if key is None or key in [str(k) for k in ((getattr(a, "spec", None) or {}).get("keys") or [])]]
        on, off = [], []
        for a in accts:
            why = LG._why_off(a)
            (off if why else on).append(LG._mask(LG._label(a)) + (f" - {LG._mask(why)[:40]}" if why else ""))
        for label, m, why in LG.missing_configured(bot):
            if m == model:
                off.append(f"{LG._mask(label)} - {LG._mask(why)[:40]}")      # red team 2026-11-25: masked like the rest
        parts = []
        if on:
            parts.append("Also on: " + ", ".join(on[:3]))
        if off:
            parts.append("Not on: " + "; ".join(off[:3]))
        return (" " + ". ".join(parts) + ".") if parts else ""
    except Exception:
        return ""


# ================================================================================================ LIT
def _lit_setup(br, d) -> dict | None:
    """Today's newest Brain setup row on this side (armed / tapped / entering first)."""
    rows = [s for s in br.get("setups") or [] if isinstance(s, dict) and (d is None or s.get("dir") == d)]
    live = [s for s in rows if s.get("status") in ("armed", "tapped", "entering")]
    return (live or rows or [None])[-1]


def lit_events(br: dict | None, sent: set, now) -> list:
    """[{"key", "step", "title", "body", "entry": bool}] new LIT lines from one Brain. Pure."""
    out = []
    br = _d(br)
    if not br or br.get("error"):
        return out
    st = _d(br.get("stage"))
    day = str(br.get("day") or _day(now))
    try:
        n = int(st.get("n") or 0)
    except (TypeError, ValueError):
        n = 0
    d = st.get("dir")
    if n >= LIT_STEPS[0] and st.get("key") not in ("trade", "done", "closed"):
        row = _lit_setup(br, d if d in (1, -1) else None)
        sid = str((row or {}).get("id") or f"{day}:{d}")
        hit = [s for s in LIT_STEPS if s <= n]
        top = hit[-1]
        k = f"setup:lit:{day}:{sid}:{top}"
        if k not in sent and not any(f"setup:lit:{day}:{sid}:{s}" in sent for s in LIT_STEPS if s > top):
            side = _side(d if d is not None else (row or {}).get("dir")) or "setup"
            out.append({"key": k, "step": top, "sid": sid, "entry": top >= ENTRY_STEP,
                        "title": f"Zlarior {side} {st.get('label') or ''} {n}/10".replace("  ", " ")[:120],
                        "body": str(st.get("waiting") or (row or {}).get("status_text") or "")[:400],
                        "also": [f"setup:lit:{day}:{sid}:{s}" for s in LIT_STEPS if s < top]})
    for row in br.get("setups") or []:
        if not isinstance(row, dict) or row.get("status") not in DEAD:
            continue
        sid = str(row.get("id") or "")
        if not sid or not any(f"setup:lit:{day}:{sid}:{s}" in sent for s in LIT_STEPS):
            continue                                   # only a setup that got a line gets its "cancelled"
        k = f"setup:lit:{day}:{sid}:cancel"
        if k not in sent:
            out.append({"key": k, "step": 0, "sid": sid, "entry": False,
                        "title": f"Zlarior {_side(row.get('dir'))} setup cancelled"[:120],
                        "body": f"Setup cancelled: {str(row.get('status_text') or row.get('status'))[:300]}"})
    return out


def score_line(br, ev: dict) -> str:
    """big-setupscore 2026-11-26: ' · Similar setups: N, won X%, avg +Y R ...' for a LIT setup line (engine/setup_score, display only:
    it never changes which trades are taken). '' for a cancel line, an unknown setup or any problem. Never raises."""
    try:
        if not ev.get("step"):
            return ""
        from . import setup_score
        row = next((s for s in (_d(br).get("setups") or []) if isinstance(s, dict) and str(s.get("id")) == str(ev.get("sid"))), None)
        ln = setup_score.line(setup_score.brain_score(row)) if row else ""
        return f"\n{ln}" if ln else ""
    except Exception:  # noqa: BLE001
        return ""


# ================================================================================================ ATLAS
def atlas_keys(bot) -> list:
    try:
        from . import live_guard as LG
        ks = []
        for a in LG.atlas_accounts(bot):
            ks += [str(k) for k in ((getattr(a, "spec", None) or {}).get("keys") or [])]
        return list(dict.fromkeys(ks))
    except Exception:
        return []


def _h(s) -> str:
    return hashlib.sha1(str(s).encode()).hexdigest()[:8]


def atlas_events(second: dict | None, keys, price, sent: set, now) -> list:
    out = []
    S = _d(_d(second).get("strategies"))
    day = _day(now)
    for k in keys or []:
        s = _d(S.get(k))
        if not s:
            continue
        short = s.get("short") or s.get("label") or k
        st = _d(s.get("state"))
        b = _d(s.get("brain"))
        stage = st.get("stage")
        if stage == "armed":
            pl = _d(b.get("plan"))
            # red team 2026-11-25: the EMA member's "Armed" text carries the live EMA 50 value (changes every 5m bar while it stays
            # armed / flips armed <-> waiting), so a text hash re-sent the same setup all day: a plan keys on entry + stop only,
            # no plan on the text with its numbers taken out (one "armed" line per member, side and wording a day)
            sid = _h(f"{pl.get('entry')}:{pl.get('stop')}") if pl else _h(re.sub(r"[0-9][0-9,.:]*", "#", str(st.get("text") or "")))
            key = f"setup:atlas:{day}:{k}:{sid}:armed"
            if key not in sent:
                extra = (f" Entry {_px(pl.get('entry'))} · stop {_px(pl.get('stop'))} · target {_px(pl.get('target'))}." if pl else "")
                out.append({"key": key, "step": "armed", "entry": False, "k": k,
                            "title": f"ATLAS {short} ARMED"[:120], "body": (str(st.get("text") or "") + extra)[:400]})
        if stage in ("in_trade", "done", "off", "error") or price is None:
            continue
        for lv in b.get("levels") or []:
            if not isinstance(lv, dict) or lv.get("px") is None or lv.get("stage") in ("taken", "used", "not known yet"):
                continue
            try:
                dist = abs(float(price) - float(lv["px"]))
            except (TypeError, ValueError):
                continue
            for pts in NEAR_PTS:
                if dist > pts:
                    continue
                key = f"setup:atlas:{day}:{k}:{lv.get('name')}:{_px(lv['px'])}:{int(pts)}"
                if key in sent:
                    continue
                if pts == NEAR_PTS[0] and f"{key[:-len(str(int(pts)))]}{int(NEAR_PTS[1])}" in sent:
                    continue
                out.append({"key": key, "step": f"{int(pts)}pts", "entry": False, "k": k,
                            "title": f"ATLAS {short}: {dist:.0f} pts from {lv.get('name') or 'its level'}"[:120],
                            "body": (f"Price {_px(price)} is {dist:.0f} pts from {lv.get('label') or lv.get('name') or 'the level'} "
                                     f"{_px(lv['px'])}: {short} arms if it sweeps it and closes back. {st.get('text') or ''}")[:400]})
                break                                   # the closest band only (10 pts implies 30)
    return out


# ================================================================================================ the driver
class SetupProgress:
    def __init__(self, send=None, clock=time.time, state_path: str | None = None):
        self._send = send
        self.clock = clock
        self.state_path = state_path or STATE_PATH
        self.sent: set = set()
        self.n: dict = {}
        self._day = None
        self.last: dict = {}

    def _load(self, day):
        if self._day == day:
            return
        self._day = day
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            d = {}
        if isinstance(d, dict) and d.get("day") == day:
            self.sent = set(d.get("sent") or [])
            self.n = {day: int(d.get("n") or 0), day + ":atlas": int(d.get("na") or 0)}
        else:
            self.sent, self.n = set(), {day: 0}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"day": self._day, "n": int(self.n.get(self._day) or 0),
                       "na": int(self.n.get(str(self._day) + ":atlas") or 0), "sent": sorted(self.sent)[-300:]}, fh)
            from .fsutil import replace as _replace
            _replace(tmp, self.state_path)
        except Exception:
            pass

    def send(self, ev: dict) -> str:
        try:
            if self._send is not None:
                return self._send(ev)
            from . import alert_bus
            return alert_bus.send_critical(ev)
        except Exception as e:  # noqa: BLE001
            return f"failed: {e.__class__.__name__}"

    def step(self, bot, now=None) -> list:
        now = float(self.clock() if now is None else now)
        done = []
        try:
            if not enabled() or bot is None or not _live_bot(bot) or not _open_hours(now):
                return done
            day = _day(now)
            self._load(day)
            evs = lit_events(getattr(bot, "brain", None), self.sent, now)
            for e in evs:
                e["body"] = (e["body"] + followers(bot, "lit") + score_line(getattr(bot, "brain", None), e))[:600]
            px = (getattr(bot, "state", None) or {}).get("price")
            for e in atlas_events(getattr(bot, "second", None), atlas_keys(bot), px, self.sent, now):
                e["body"] = (e["body"] + followers(bot, "atlas", e.get("k")))[:600]
                evs.append(e)
            changed = False
            for e in evs:
                quiet = _quiet(now) and not e["entry"]
                capped = (int(self.n.get(day) or 0) >= DAY_MAX or (str(e["key"]).startswith("setup:atlas:")
                          and int(self.n.get(day + ":atlas") or 0) >= ATLAS_MAX)) and not e["entry"]
                if quiet or capped:
                    r = "held: quiet hours" if quiet else f"held: {DAY_MAX} today"
                else:
                    r = self.send({"kind": "setup", "key": e["key"], "title": e["title"], "body": e["body"],
                                   "notify_type": TYPE, "soft": not e["entry"]})
                    if r in ("queued", "sent", "dup"):
                        self.n[day] = int(self.n.get(day) or 0) + 1
                        if str(e["key"]).startswith("setup:atlas:"):
                            self.n[day + ":atlas"] = int(self.n.get(day + ":atlas") or 0) + 1
                self.sent.add(e["key"])
                self.sent.update(e.get("also") or [])
                changed = True
                done.append((e["key"], r))
            if changed:
                self._save()
            self.last = {"t": int(now), "sent": done[-4:], "n": self.n.get(day)}
        except Exception as e:  # noqa: BLE001
            self.last = {"t": int(now), "error": f"{e.__class__.__name__}: {e}"}
        return done
