"""Alerts plus (research/writeups/competitor-features.md items 1, 3, 4, 5): read-only notices, never an order.

  1. setup armed      a push when the LIT limit arms and when the 1m-CISD wait starts ("LIT setup armed: LONG limit 29,842 ·
                      stop 29,807.5 · target 30,118 · ~6 micros ($504 risk) · valid until 03:15"), and "Setup expired — no
                      fill" when it lapses. Keys armed:/armed1m:/expired:<arm_t>:<dir>, the same on the PC and the cloud, so
                      one side's relay "sent" marker stops the other. PC: LiveBot._alerts_tick -> pc_setup_tick (after
                      routing, the push in a thread); cloud: tools/cloud_monitor.py (setup_step on its state).
  2. critical repeat  crit_step: an active critical condition is pushed, then repeated every 10 min (at most 6 sends) until
                      the owner taps "Got it" in the phone app (the app posts {"le": "ack", "id"} to the free ntfy relay,
                      engine/push.Relay, which both senders read) or the condition clears by itself (then one quiet
                      "resolved" notice replaces it). Kinds: Surface offline (cloud), FEED STALE in session, position
                      mismatch / reconcile flatten, kill switch, eval room < $400, clock drift block, update failed / rolled
                      back (PC: the bot puts them in its heartbeat "crit", engine/ops_checks --tick repeats them).
  3. stale cloud      cloud_step (ops tick): the dashboard branch (the cloud monitor's publish) unchanged for 45+ min on a
                      weekday 02:15-16:30 ET -> one push, one "back" push. Cheap: `git ls-remote` each tick, a depth-1 fetch
                      of state.json only when the branch moved.
  4. rules check      rules_fp: a short hash of live_model.json "lit" + "lit_sizing" (eval_start left out: the PC start cfg may
                      override it) + the trading code (engine/lit.py, lit_live.py, sizing.py, lit_fills.py, eval_life.py,
                      line endings ignored). In the heartbeat ("rules") and the cloud state ("rules"); the cloud pushes once
                      per mismatch pair (rules_step).
Levels: every kind here is on / silent / off (KINDS), set in the phone app (tools/web_public/alerts.js posts {"le": "prefs"}
to the relay; the cloud keeps the last one in state.json "push_prefs", the PC's ops tick in data/push_prefs.json).
Everything here is pure or failure-safe: no function raises into the bot's loop, nothing changes what the bot trades.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "alerts_plus.json")     # PC: open setups seen (gitignored)
PREFS_PATH = os.path.join(ROOT, "data", "push_prefs.json")      # PC: the phone's levels, written by the ops tick (gitignored)

KINDS = {   # kind: (label for the app, what it covers, critical = repeats until "Got it")
    "armed": ("Setup armed / expired", "LIT limit armed, 1m-CISD wait, setup expired without a fill", False),
    "pc_offline": ("Surface offline", "no heartbeat from the PC in the session (cloud)", True),
    "feed_stale": ("FEED STALE", "NinjaTrader bars missing / stale in an entry window: new entries blocked", True),
    "unprotected": ("Position mismatch", "NinjaTrader position vs the bot's ledger, reconcile flatten", True),
    "kill": ("Kill switch fired", "the bot flattened and stopped", True),
    "eval_floor": ("Eval near the floor", "room to the trailing max-loss floor below $400", True),
    "clock": ("Clock drift", "PC clock off: entries blocked", True),
    "update": ("Update failed", "bot auto-update failed or rolled back", True),
    "cloud_stale": ("Cloud monitor stale", "the cloud monitor has not published for 45+ min in market hours", False),
    "rules": ("Rules differ", "PC and cloud run different LIT rules", False),
    "second": ("ATLAS (PAPER)", "ATLAS (EMA / MACD / S/R) paper entries and exits next to LIT, never traded (cloud)", False),
    # engine/ai_watch.py (2026-10-22)
    "freeze": ("Feed frozen in a trade", "a position is open and the NinjaTrader 1m bars stopped (3+ min)", True),
    "anomaly": ("Anomaly", "price spike / bad tick on the 1m feed, an entry routed 30+ s after its signal", False),
    "drift": ("Drift", "LIT / account B live results below the backtest's expected range, execution drift", False),
    "loss_cap": ("Both accounts loss", "LIT + account B together at the combined daily / weekly cap", False),
    "rules_change": ("Rules changed", "the trading rules the PC bot runs changed (who / when / why)", False),
}
LEVELS = ("on", "silent", "off")
REPEAT_S = 10 * 60
REPEAT_MAX = 6
ARM_MAX_AGE_S = 45 * 60
CLOUD_STALE_S = 45 * 60
CLOUD_WINDOW = (135, 990)            # 02:15-16:30 ET, weekdays (the cloud runs 01:32 + every 30 min 02:02-16:32 ET)
ROOM_FLOOR_USD = 400.0
RULE_CODE = ("lit.py", "lit_live.py", "sizing.py", "lit_fills.py", "eval_life.py")
_ID_RX = re.compile(r"[^\w\-:.]")


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def _hm(t) -> str:
    try:
        return _et(t).strftime("%H:%M")
    except Exception:
        return "?"


def px(x) -> str:
    """29,842 / 29,807.5 / 29,807.25 (no trailing zeros)."""
    s = f"{float(x):,.2f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def safe_id(s) -> str:
    return _ID_RX.sub("_", str(s))[:80]


def _read(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"), default=str)
        os.replace(tmp, path)
    except Exception:
        pass


# ============================================================================================ levels (on / silent / off)
def level(prefs: dict | None, kind: str) -> str:
    v = (prefs or {}).get(kind)
    return v if v in LEVELS else "on"


def apply_level(payload: dict, prefs: dict | None) -> dict | None:
    """None = off (record only); silent -> the phone shows it without sound (payload "silent")."""
    lv = level(prefs, payload.get("kind"))
    if lv == "off":
        return None
    if lv == "silent":
        return {**payload, "silent": True}
    return payload


def prefs_from(msgs, stored: dict | None = None) -> dict:
    """The newest {"le": "prefs"} relay message vs the stored one: {"t", "prefs"}. Unknown kinds / levels are dropped."""
    best = dict(stored or {}) if isinstance(stored, dict) else {}
    for m in msgs or []:
        if m.get("le") != "prefs" or not isinstance(m.get("prefs"), dict):
            continue
        t = int(m.get("_t") or m.get("t") or 0)
        if t >= int(best.get("t") or 0):
            best = {"t": t, "prefs": {k: v for k, v in m["prefs"].items() if k in KINDS and v in LEVELS}}
    return best


def acks_from(msgs) -> dict:
    """{alert id: newest ack time} from the relay's {"le": "ack", "id"} messages (the phone's "Got it")."""
    out = {}
    for m in msgs or []:
        if m.get("le") == "ack" and m.get("id"):
            t = int(m.get("_t") or m.get("t") or 0)
            k = safe_id(m["id"])
            out[k] = max(out.get(k, 0), t)
    return out


# ============================================================================================ 1. setup armed / expired
def _side(d) -> str:
    return "LONG" if int(d) == 1 else "SHORT"


def est_size(limit, stop, target, size_fn=None, now=None, d=1) -> tuple[int | None, float | None]:
    """(~micros, $ risk) at the limit price. size_fn(trade_like) -> micros (the side's own sizing: lit_sizing mode, room);
    without it the LIT rule ($800 up to 20 pts, 800x20/stop, max 40). Never raises."""
    try:
        risk = abs(float(limit) - float(stop))
        if risk <= 0:
            return None, None
        tr = {"entry_t": int(now or time.time()), "dir": int(d), "entry": float(limit), "stop": float(stop), "stop0": float(stop),
              "target": float(target) if target is not None else None, "risk_pts": risk,
              "tgt_pts": abs(float(target) - float(limit)) if target is not None else None, "est": True, "size_why": []}
        if size_fn is not None:
            q = int(size_fn(tr) or 0)
        else:
            from . import lit
            q = int(lit.qty_for(risk))
        return q, round(q * risk * 2.0, 0)
    except Exception:
        return None, None


def armed_payload(src: str, s: dict, stage: str, now, size=(None, None)) -> dict:
    from . import push
    side = _side(s["dir"])
    q, usd = size
    sz = f" · ~{q} micro{'s' if q != 1 else ''} (${usd:,.0f} risk)" if q else ""
    tgt = f" · target {px(s['target'])}" if s.get("target") is not None else ""
    if stage == "1m":
        line = f"{side} limit {px(s['limit'])} tapped, waiting for a 1m CISD · stop {px(s['stop'])}{tgt}{sz} · valid until {_hm(s['valid'])}"
        key = f"armed1m:{s['arm_t']}:{s['dir']}"
    else:
        line = f"{side} limit {px(s['limit'])} · stop {px(s['stop'])}{tgt}{sz} · valid until {_hm(s['valid'])}"
        key = f"armed:{s['arm_t']}:{s['dir']}"
    p = push.text_payload(src, "armed", f"LIT setup armed · {side}", f"LIT setup armed: {line}", key=key, t=now, url="#/today")
    p.update(tag=f"le-setup-{int(s['arm_t'])}", side=side, entry=s["limit"], stop=s["stop"], target=s.get("target"),
             qty=q, risk_usd=usd, setup="LIT")
    return p


def expired_payload(src: str, s: dict, now) -> dict:
    from . import push
    side = _side(s["dir"])
    p = push.text_payload(src, "armed", "Setup expired — no fill",
                          f"{side} limit {px(s['limit'])} (armed {_hm(s['arm_t'])} ET) expired at {_hm(now)} ET without a fill. "
                          "No trade from it.", key=f"expired:{s['arm_t']}:{s['dir']}", t=now, url="#/today")
    p.update(tag=f"le-setup-{int(s['arm_t'])}", side=side)
    return p


def _filled(s: dict, state: dict, trades) -> bool:
    a, d = int(s["arm_t"]), int(s["dir"])
    for x in ((state or {}).get("position"), (state or {}).get("enter_now")):
        if isinstance(x, dict) and int(x.get("entry_t") or 0) >= a and int(x.get("dir") or 0) == d:
            return True
    return any(int(t.get("entry_t") or 0) >= a and int(t.get("dir") or 0) == d for t in trades or [])


def setup_step(prev: dict | None, state: dict | None, now, trades=(), size_fn=None, src: str = "PC", cisd1m: int = 20,
               enabled: bool = True) -> tuple[dict, list]:
    """One look at the live state's LIT setups (engine/lit_live state "setups": arm_t, limit, stop, target, expires_t,
    tapped_t). prev = {"open": {id: setup}} from the last look. Returns (new prev, payloads): armed (new setup), armed1m (the
    limit was tapped: the 1m-CISD wait started), expired (gone without an entry). enabled False (the market is closed, the
    session is over, a test harness) = track only."""
    now = int(now)
    prev = prev if isinstance(prev, dict) else {}
    seen = prev.get("open") or {}
    cur, out = {}, []
    for side, s in ((state or {}).get("setups") or {}).items():
        try:
            d = 1 if side == "long" else -1
            arm = int(s["arm_t"])
            tapped = s.get("tapped_t")
            stage = "1m" if tapped else "limit"
            valid = int(tapped) + 60 * int(cisd1m or 20) if tapped else int(s.get("expires_t") or arm + 1800)
            row = {"arm_t": arm, "dir": d, "stage": stage, "limit": float(s["limit"]), "stop": float(s["stop"]),
                   "target": None if s.get("target") is None else float(s["target"]), "valid": valid}
        except Exception:
            continue
        sid = f"{arm}:{d}"
        cur[sid] = row
        old = seen.get(sid)
        if not enabled or valid <= now:
            continue
        if old is None and now - arm <= ARM_MAX_AGE_S:
            out.append(armed_payload(src, row, stage, now, est_size(row["limit"], row["stop"], row["target"], size_fn, now, d)))
        elif old is not None and old.get("stage") == "limit" and stage == "1m":
            out.append(armed_payload(src, row, stage, now, est_size(row["limit"], row["stop"], row["target"], size_fn, now, d)))
    for sid, old in seen.items():
        if sid in cur or not enabled:
            continue
        try:
            if not _filled(old, state, trades) and now - int(old["arm_t"]) <= 3 * 3600:
                out.append(expired_payload(src, old, now))
        except Exception:
            continue
    return {"open": cur, "t": now}, out


# PC side: LiveBot._alerts_tick (once per poll, after routing) -> here
_PC = {"prev": None, "lock": threading.Lock()}


def pc_size_fn(bot):
    """The bot's own LIT sizing for an estimate (engine/sizing.lit_qty with the lit_sizing mode, the eval room and state);
    no logging, no learning side effects."""
    def f(tr):
        from . import lit, sizing
        lsz = getattr(bot, "_lit_sizing", None) or {}
        mode = lsz.get("mode")
        room = bot.eval_room() if mode in ("safe_eval", "eval", "two_week") else None
        st = bot.eval_state() if mode in ("two_week", "eval", "safe_eval", "fast_eval") else None
        r = sizing.lit_qty(int(lit.qty_for(tr["risk_pts"])), tr, lsz, room=room, state=st, learning=None)
        return int(r.get("qty") or 0)
    return f


def prefs_cached(path: str = PREFS_PATH) -> dict:
    return (_read(path).get("prefs") or {}) if path else {}


def pc_send(payload: dict, prefs: dict | None = None):
    """PC push in a background thread (never delays routing): level, de-dup by key (data/push_sent.json), skip when the cloud
    already sent the same key (relay "sent" marker), mark ours. Never raises."""
    def run():
        try:
            from . import push
            p = apply_level(payload, prefs if prefs is not None else prefs_cached())
            n = push.pc_notifier()
            if p is None:
                n.mark(payload)
                n._save()
                return
            n.cfg = push.pc_config()
            if not push.enabled(n.cfg):
                n.mark(payload)
                n._save()
                return
            other = n.relay.sent_keys() if n.relay is not None else set()
            r = n.notify(p, push_it=True, other_sent=other)
            if r.get("sent") and n.relay is not None:
                n.relay.post({"le": "sent", "key": p["key"], "src": "pc", "t": int(time.time())})
        except Exception:
            pass
    try:
        from . import push
        if push.pc_notifier().seen(payload):
            return {"dup": True}
        threading.Thread(target=run, name="push-plus", daemon=True).start()
        return {"queued": True}
    except Exception:
        return None


def pc_setup_tick(bot, now, send=pc_send, path: str = STATE_PATH) -> list:
    """Setup armed / expired for the PC bot. Only while the bot can trade (running, market open, LIT). Never raises."""
    try:
        st = getattr(bot, "state", None) or {}
        if st.get("model") != "lit":
            return []
        with _PC["lock"]:
            if _PC["prev"] is None:
                _PC["prev"] = _read(path).get("setups") or {}
            cis = ((st.get("strategy") or {}).get("params") or {}).get("cisd1m") or 20
            on = bool((getattr(bot, "health", None) or {}).get("market_open", True)) and not getattr(bot, "kill", False)
            new, pays = setup_step(_PC["prev"], st, now, trades=None, size_fn=pc_size_fn(bot), src="PC", cisd1m=cis, enabled=on)
            changed = new.get("open") != (_PC["prev"] or {}).get("open")
            _PC["prev"] = new
            if changed:
                _write(path, {**_read(path), "setups": new})
        for p in pays:
            p["account"] = bot._push_account() if callable(getattr(bot, "_push_account", None)) else ""
            send(p)
        return pays
    except Exception:
        return []


# ============================================================================================ 2. critical alerts that repeat
def crit_payload(src: str, cid: str, cur: dict, now, lv: str = "on") -> dict:
    from . import push
    n = int(cur["n"])
    rep = f"Repeat {n}/{REPEAT_MAX}: " if n > 1 else ""
    p = push.text_payload(src, cur["kind"], cur["title"], f"{rep}{cur['body']} Tap Got it in the app to stop the repeats.",
                          key=f"crit:{cid}:{n}", t=now, url=f"#/ack/{cid}")
    p.update(tag=f"le-crit-{hashlib.sha1(cid.encode()).hexdigest()[:10]}", require=True, ack=cid, level="critical")
    if lv == "silent":
        p["silent"] = True
    return p


def cleared_payload(src: str, cid: str, cur: dict, now) -> dict:
    from . import push
    p = push.text_payload(src, cur["kind"], f"Resolved: {cur['title']}", f"Cleared by itself at {_hm(now)} ET. Nothing to do.",
                          key=f"crit_clear:{cid}:{int(cur.get('first') or 0)}", t=now, url="#/ack")
    p.update(tag=f"le-crit-{hashlib.sha1(cid.encode()).hexdigest()[:10]}", silent=True)
    return p


def crit_step(st: dict | None, active, acks: dict | None, now, prefs: dict | None = None, src: str = "PC") -> tuple[dict, list]:
    """One repeat step. st = {id: {"kind", "title", "body", "first", "n", "last", "acked"}} from the last step; active = list
    (or dict by id) of {"id", "kind", "title", "body"} (+ "sent_at": the first notice was already pushed elsewhere, e.g. the
    cloud's own Surface-offline push); acks = acks_from(relay). A new condition is pushed at once, then every REPEAT_S until
    REPEAT_MAX sends, an ack newer than the condition's start, or the condition clears (one quiet "resolved" notice when it
    was pushed and not acked). Level off: tracked, never sent; silent: sent once, no sound, no repeats."""
    now = int(now)
    st = st if isinstance(st, dict) else {}
    acks = acks or {}
    act = active if isinstance(active, dict) else {safe_id(a["id"]): a for a in active or [] if a.get("id") and a.get("kind")}
    new, out = {}, []
    for cid, a in act.items():
        cid = safe_id(cid)
        cur = dict(st.get(cid) or {})
        if not cur:
            cur = {"kind": a["kind"], "first": now, "n": 0, "last": 0}
            if a.get("sent_at"):
                cur.update(n=1, last=int(a["sent_at"]))
        cur["kind"], cur["title"], cur["body"] = a["kind"], str(a.get("title") or cur.get("title") or a["kind"])[:120], \
            str(a.get("body") or cur.get("body") or "")[:400]
        if not cur.get("acked") and acks.get(cid, 0) >= int(cur["first"]) - 60:
            cur["acked"] = int(acks[cid])
        lv = level(prefs, a["kind"])
        due = cur["n"] == 0 or (lv == "on" and now - int(cur["last"]) >= REPEAT_S - 60)
        if not cur.get("acked") and lv != "off" and cur["n"] < REPEAT_MAX and due:
            cur["n"] += 1
            cur["last"] = now
            out.append(crit_payload(src, cid, cur, now, lv))
        new[cid] = cur
    for cid, cur in st.items():
        if cid not in new and cur.get("n") and not cur.get("acked"):
            out.append(cleared_payload(src, cid, cur, now))
    return new, out


def crit_open(st: dict | None) -> list:
    """The phone's ack list: open, not acked alerts (id, kind, title, body, first, n)."""
    return [{"id": k, **{x: v.get(x) for x in ("kind", "title", "body", "first", "n")}}
            for k, v in sorted((st or {}).items(), key=lambda kv: kv[1].get("first") or 0) if not v.get("acked")]


def _trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def pc_conditions(bot, now=None) -> list:
    """The PC's critical conditions right now (the heartbeat's "crit", repeated by the ops tick). Never raises."""
    out = []
    try:
        now = int(now or time.time())
        h = getattr(bot, "health", None) or {}
        day = _trading_day(now)
        running = bool(getattr(bot, "running", False))
        if running and h.get("feed_block") and h.get("market_open"):
            out.append({"id": f"feed_stale:{day}", "kind": "feed_stale", "title": "FEED STALE: new entries blocked",
                        "body": f"NinjaTrader bars missing or stale ({str(h['feed_block'])[:100]}). Check NinjaTrader is connected "
                                "and the chart with LE_BarFeed is open."})
        rc = getattr(bot, "_recon", None)
        if isinstance(rc, dict) and rc.get("pushed"):
            exp, net = (rc.get("sig") or (0, 0))[:2]
            hand = int(rc.get("flat_tries") or 0) >= 3
            out.append({"id": f"unprotected:{day}:{exp}:{net}", "kind": "unprotected",
                        "title": "FLATTEN BY HAND" if hand else "Position mismatch: check NinjaTrader",
                        "body": (f"NinjaTrader holds {net:+d} micros, the bot's ledger {exp:+d}. "
                                 + ("3 CLOSEPOSITION tries failed: NinjaTrader > Flatten Everything." if hand else
                                    "The bot is closing it (reconcile flatten)." if exp == 0 else "Check the stop / target in NinjaTrader."))})
        if getattr(bot, "kill", False):
            out.append({"id": f"kill:{day}", "kind": "kill", "title": "KILL SWITCH fired",
                        "body": "The bot flattened and stopped; no new orders today. Check NinjaTrader shows flat."})
        lsz = getattr(bot, "_lit_sizing", None) or {}
        if lsz.get("mode") in ("two_week", "eval", "safe_eval", "fast_eval") and callable(getattr(bot, "eval_room", None)):
            room = float(bot.eval_room())
            if 0 < room < ROOM_FLOOR_USD:
                start = bot.eval_start() if callable(getattr(bot, "eval_start", None)) else ""
                out.append({"id": f"eval_floor:{start or '-'}", "kind": "eval_floor", "title": f"Eval near the floor: ${room:,.0f} left",
                            "body": f"${room:,.0f} to the trailing max-loss floor. One stop-out can end the eval; check the size."})
        if h.get("guard_block"):
            out.append({"id": f"clock:{day}", "kind": "clock", "title": "Clock drift: entries blocked",
                        "body": f"{str(h['guard_block'])[:120]}. Windows: Settings > Time > Sync now."})
        try:
            from . import ai_watch
            out += ai_watch.crit_conditions(bot, now)          # the feed frozen mid-trade (engine/ai_watch.py)
        except Exception:
            pass
        try:
            from . import autoupdate
            u = autoupdate.status()
            if u.get("result") in ("failed", "rolled_back") and u.get("last_check_t"):
                out.append({"id": f"update:{int(u['last_check_t'])}", "kind": "update",
                            "title": "Bot update failed" + (", rolled back" if u["result"] == "rolled_back" else ""),
                            "body": f"{str(u.get('reason') or '')[:160]} Run UPDATE.bat by hand or tell Claude."})
        except Exception:
            pass
    except Exception:
        pass
    return out


# ============================================================================================ 3. stale cloud (PC watches it)
def cloud_window(now) -> bool:
    e = _et(now)
    m = e.hour * 60 + e.minute
    if e.weekday() >= 5 or not (CLOUD_WINDOW[0] <= m <= CLOUD_WINDOW[1]):
        return False
    try:
        from . import guards
        return not guards.full_closure(e.strftime("%Y-%m-%d"))
    except Exception:
        return True


def cloud_step(prev: dict | None, ref: dict | None, now) -> tuple[dict, list]:
    """prev = {"sha", "last_t", "alerted", "back"}; ref = {"sha", "t" (the publish time; None = unknown, then the time the
    PC first saw this sha)} or None (could not ask GitHub: internet down -> no change). Returns (new prev, payloads)."""
    from . import push
    now = int(now)
    prev = dict(prev or {})
    if not ref or not ref.get("sha"):
        return prev, []
    out = []
    if ref["sha"] != prev.get("sha"):
        if prev.get("alerted"):
            out.append({**push.text_payload("PC", "cloud_stale", "Cloud monitor back",
                                            f"The cloud monitor published again at {_hm(ref.get('t') or now)} ET.",
                                            key=f"cloud_back:{prev.get('last_t')}", t=now, url="#/today"), "tag": "le-cloud-stale"})
        prev = {"sha": ref["sha"], "last_t": int(ref.get("t") or now)}
    elif ref.get("t") and int(ref["t"]) > int(prev.get("last_t") or 0):
        prev["last_t"] = int(ref["t"])
    age = now - int(prev.get("last_t") or now)
    prev["age_s"] = age
    prev["stale"] = bool(age >= CLOUD_STALE_S and cloud_window(now))
    if prev["stale"] and not prev.get("alerted"):
        prev["alerted"] = now
        out.append({**push.text_payload("PC", "cloud_stale", f"Cloud monitor has not run for {age // 60} min",
                                        f"Last publish {_hm(prev['last_t'])} ET. The paper bot and the Surface-offline alarm are "
                                        "blind until it runs: GitHub > Actions > cloud-monitor (Run workflow).",
                                        key=f"cloud_stale:{prev['last_t']}", t=now, url="#/today"), "tag": "le-cloud-stale"})
    return prev, out


def cloud_ref(cwd: str = ROOT, prev: dict | None = None, run=None) -> dict | None:
    """The dashboard branch's sha (`git ls-remote`, cheap) and, when it moved, its state.json (depth-1 fetch into a private
    ref): {"sha", "t" (state last_run or the commit time), "rules", "prefs"}. None = GitHub unreachable. Never raises."""
    import subprocess

    def sh(args, timeout=60):
        if run is not None:
            return run(args)
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    try:
        code, outp = sh(["ls-remote", "origin", "refs/heads/dashboard"], 30)
        if code or not outp.strip():
            return None
        sha = outp.split()[0]
        if prev and prev.get("sha") == sha:
            return {"sha": sha, "t": prev.get("last_t")}
        ref = "refs/le/cloud-dashboard"
        code, _ = sh(["fetch", "-q", "--depth", "1", "origin", f"+refs/heads/dashboard:{ref}"])
        if code:
            return {"sha": sha, "t": None}
        out = {"sha": sha, "t": None}
        code, st = sh(["show", f"{ref}:state.json"], 30)
        if not code:
            try:
                s = json.loads(st)
                out.update(t=int(s.get("last_run") or 0) or None, rules=s.get("rules"), prefs=s.get("push_prefs"))
            except Exception:
                pass
        if not out["t"]:
            code, ct = sh(["log", "-1", "--format=%ct", ref], 30)
            if not code and ct.strip().isdigit():
                out["t"] = int(ct.strip())
        return out
    except Exception:
        return None


# ============================================================================================ 4. PC-vs-cloud rules check
_CODE = {"key": None, "hash": None}


def code_hash(root: str = ROOT) -> str:
    """Short hash of the trading code (line endings ignored, so a Windows checkout hashes like Linux)."""
    paths = [os.path.join(root, "engine", f) for f in RULE_CODE]
    try:
        key = tuple((p, os.path.getmtime(p), os.path.getsize(p)) for p in paths if os.path.exists(p))
    except Exception:
        key = None
    if key is not None and key == _CODE["key"]:
        return _CODE["hash"]
    h = hashlib.sha1()
    for p in paths:
        try:
            with open(p, "rb") as fh:
                h.update(fh.read().replace(b"\r\n", b"\n"))
        except Exception:
            h.update(b"-")
    _CODE.update(key=key, hash=h.hexdigest()[:6])
    return _CODE["hash"]


def rules_fp(lit: dict | None, lit_sizing: dict | None, model: str = "lit", root: str = ROOT) -> dict:
    """{"hash", "rules", "code", "model"}: hash of the LIT settings + sizing (eval_start excluded) + the trading code."""
    ls = {k: v for k, v in (lit_sizing or {}).items() if k != "eval_start"}
    blob = json.dumps({"model": model, "lit": lit or {}, "lit_sizing": ls}, sort_keys=True, separators=(",", ":"), default=str)
    rules = hashlib.sha1(blob.encode()).hexdigest()[:6]
    code = code_hash(root)
    return {"hash": hashlib.sha1(f"{rules}:{code}".encode()).hexdigest()[:6], "rules": rules, "code": code, "model": model}


def model_rules(lm: dict | None = None) -> dict:
    """live_model.json as the cloud runs it."""
    if lm is None:
        from .lab_adapter import live_model
        lm = live_model()
    m = lm.get("model") or "lit"
    return rules_fp(lm.get("lit") if m == "lit" else lm.get("params"), lm.get("lit_sizing") if m == "lit" else None, m)


def pc_rules(bot) -> dict | None:
    """What the PC bot runs: its start cfg's overrides, else live_model.json. Never raises."""
    try:
        from .lab_adapter import engine_model, live_model
        cfg = getattr(bot, "cfg", None) or {}
        lm = live_model()
        m = cfg.get("model") or lm.get("model") or "lit"
        if m == "engine" and lm.get("model") != "engine":
            lm = engine_model()
        if m == "lit":
            return rules_fp(cfg.get("model_params") or lm.get("lit"), cfg.get("lit_sizing") or lm.get("lit_sizing"), m)
        return rules_fp(cfg.get("params") or lm.get("params"), None, m)
    except Exception:
        return None


def rules_step(prev: dict | None, pc: dict | None, cloud: dict | None, now, pc_fresh: bool = True) -> tuple[dict, list]:
    """The cloud's check of the heartbeat's "rules" against its own: one push per mismatch pair."""
    from . import push
    prev = dict(prev or {})
    if not pc_fresh or not isinstance(pc, dict) or not pc.get("hash") or not isinstance(cloud, dict):
        return prev, []
    if pc["hash"] == cloud.get("hash"):
        return {"same": True, "pc": pc["hash"], "cloud": cloud["hash"], "t": int(now), "key": None}, []
    key = f"rules:{pc['hash']}:{cloud['hash']}"
    new = {"same": False, "pc": pc["hash"], "cloud": cloud["hash"], "t": int(now), "key": key}
    if prev.get("key") == key:
        return new, []
    what = [w for w, a, b in (("model", pc.get("model"), cloud.get("model")), ("settings", pc.get("rules"), cloud.get("rules")),
                              ("code", pc.get("code"), cloud.get("code"))) if a != b]
    p = push.text_payload("Cloud", "rules", "PC and cloud run different rules",
                          f"PC and cloud run different rules: PC {pc['hash']} / cloud {cloud['hash']} — update the Surface "
                          f"(different: {', '.join(what) or '?'}). Paper and PC results are not comparable until then.",
                          key=key, t=now, url="#/today")
    p["tag"] = "le-rules"
    return new, [p]


# ============================================================================================ PC ops tick (engine/ops_checks)
def ops_tick(ctx: dict, state: dict, now, send, real: bool) -> list:
    """engine/ops_checks.tick hook (every 5 min): read the relay (acks, levels), repeat the heartbeat's critical alerts,
    watch the cloud monitor. send(payload) = ops_checks.send (de-dup by key, LE_OPS_PUSH). Never raises."""
    out = []
    try:
        from . import push
        A = state.setdefault("alerts_plus", {})
        relay = push.Relay(timeout=6.0) if real else None
        msgs = relay.read() if relay is not None else list(ctx.get("relay_msgs") or [])
        # the phone's levels: the newest of the relay, our stored copy and the cloud's (state.json "push_prefs")
        base = A.get("prefs") or {}
        cp = (A.get("cloud") or {}).get("prefs") or {}
        if isinstance(cp, dict) and int(cp.get("t") or 0) > int(base.get("t") or 0):
            base = cp
        A["prefs"] = prefs_from(msgs, base)
        prefs = (A["prefs"] or {}).get("prefs") or {}
        if real:
            _write(PREFS_PATH, A["prefs"])
        acks = acks_from(msgs)
        hb = ctx.get("hb") or {}
        saved = float(hb.get("_saved_t") or hb.get("t") or 0)
        pays = []
        if hb and now - saved <= 15 * 60:            # the bot's conditions are fresh: repeat / clear them
            before = A.get("crit") or {}
            A["crit"], cp = crit_step(before, hb.get("crit") or [], acks, now, prefs, src="PC")
            pays += cp
            if relay is not None and (cp or crit_open(before) != crit_open(A["crit"])):
                relay.post({"le": "crit", "src": "pc", "open": crit_open(A["crit"]), "t": int(now)})
        cref = cloud_ref(prev=A.get("cloud")) if real else ctx.get("cloud_ref")
        if real or "cloud_ref" in ctx:
            c_prev = A.get("cloud") or {}
            A["cloud"], cpays = cloud_step(c_prev, cref, now)
            if cref and cref.get("rules"):
                A["cloud"]["rules"] = cref["rules"]
            elif c_prev.get("rules"):
                A["cloud"]["rules"] = c_prev["rules"]
            if cref and cref.get("prefs"):
                A["cloud"]["prefs"] = cref["prefs"]
            pays += cpays
        for p in pays:
            q = apply_level(p, prefs)
            if q is None:
                state.setdefault("sent", {})[p["key"]] = int(now)
                out.append({"key": p["key"], "skipped": "off"})
                continue
            r = send(q)
            out.append({"key": p["key"], "title": p["title"], **{k: r.get(k) for k in ("sent", "dup", "skipped", "error")}})
    except Exception as e:
        out.append({"key": "alerts_plus", "error": e.__class__.__name__})
    return out


def hb_block(bot) -> dict:
    """The heartbeat's two fields: "rules" (what the PC runs) and "crit" (its critical conditions now). Never raises."""
    try:
        return {"rules": pc_rules(bot), "crit": pc_conditions(bot)}
    except Exception:
        return {"rules": None, "crit": []}
