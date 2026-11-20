"""Phone alert self-check (owner 2026-11-20: "notifications for trade entries I never got one from today. And results").

Which routes a real trade's ENTRY and RESULT alert has on this PC (the Olympus phone app, the private ntfy alert topic), what is
missing, and one TEST entry + one TEST close on every route, so the iPhone shows which route works: Olympus, the ntfy app, both or
neither. The test uses the real alerts' words and $ (engine/notify.entry_message / exit_message, the same quiet-hours sound rules),
says "TEST, no trade" in the text, is never recorded as a trade (the 15-minute report's matching is untouched) and costs 2 ntfy posts
(counted in the day's budget). At most one test a minute (TEST_COOLDOWN_S), and the ntfy half is skipped when those 2 posts would
eat into the room kept for trade alerts (ntfy_room: tools/pc_report TRADE_ALERT_RESERVE, this PC's count and ntfy's own).

    python -X utf8 -m engine.alert_check          the routes + what is missing (nothing is sent)
    python -X utf8 -m engine.alert_check --test   + the TEST alerts, and what each route answered

The PC dashboard's Settings > Phone app notifications > Send test (server.py /api/push/test) runs the same test.
Nothing here can place, change or cancel an order. Never prints a topic, a key or an account id.
"""
from __future__ import annotations

import sys
import threading
import time

TEST_WORDS = "TEST, no trade was placed."
TEST_NTFY_POSTS = 2             # a TEST entry + a TEST close
TEST_COOLDOWN_S = 60            # one test a minute: the PC dashboard has no login on the home network / Tailscale, and each test
                                # spends 2 of ntfy's ~250 posts a day that the trade alerts need
_TEST = {"t": None}
_TEST_LOCK = threading.Lock()


def routes(ntfy_cfg=None) -> dict:
    """{"phones", "crypto", "ntfy", "trade_opened", "trade_closed", "ring_at_night", "trade_routes", "warn": [plain sentences], "ok"}. ntfy_cfg: the
    private topic {"ntfy", "topic"} (tests); None = this PC's (engine/notify.alert_cfg). Never raises."""
    from . import notify, push
    out = {"phones": 0, "crypto": False, "ntfy": False, "trade_opened": True, "trade_closed": True, "ring_at_night": False,
           "trade_routes": "both", "warn": [], "ok": False}
    try:
        out["crypto"] = push.crypto_ok()
        if push.own_key(make=False):                 # no key yet = no phone; a look never makes one (sending does)
            c = push.pc_config()
            out["phones"] = len(c.get("subs") or []) if push.enabled(c) else 0
    except Exception:
        pass
    try:
        out["ntfy"] = bool((notify.alert_cfg() if ntfy_cfg is None else ntfy_cfg or {}).get("topic"))
    except Exception:
        pass
    try:
        s = notify.settings()
        out["trade_opened"], out["trade_closed"] = notify.on("trade_opened", s), notify.on("trade_closed", s)
        out["ring_at_night"] = all(notify.rings(k, s) for k in notify.TRADE_RING)
        out["trade_routes"] = notify.trade_routes(s)
    except Exception:
        pass
    w = out["warn"]
    if not out["phones"] and not out["ntfy"]:
        w.append("NO ROUTE: this PC has no Olympus phone and no private ntfy alert topic, so trade alerts reach nobody. Fix: on the "
                 "iPhone open Olympus from the Home Screen and tap Allow notifications; and on the PC run "
                 "python tools/pc_report.py --setup, then follow that topic in the ntfy app.")
    elif not out["ntfy"]:
        w.append("Only the Olympus app: no ntfy backup topic on this PC (python tools/pc_report.py --setup adds one).")
    elif not out["phones"]:
        w.append("Only ntfy: no Olympus phone yet (open Olympus from the iPhone's Home Screen, tap Allow notifications).")
    if not out["crypto"]:
        w.append("The Python package 'cryptography' is missing: no Olympus app alerts (ntfy still works).")
    for k, word in (("trade_opened", "entry"), ("trade_closed", "result")):
        if not out[k]:
            w.append(f"{k} is OFF in notify_settings.json: no {word} alerts.")
    if not out["ring_at_night"]:
        w.append("Trade alerts come without sound 23:00-07:00 ET, they still show (to ring: add trade_opened / trade_closed to "
                 "ring_in_quiet_hours in notify_settings.json).")
    if out.get("trade_routes") in ("olympus", "ntfy"):
        w.append(f"trade_routes is '{out['trade_routes']}' in notify_settings.json: trades and the important alerts go there first, "
                 "the other app only when that one did not take it.")
    out["ok"] = bool(out["phones"] or out["ntfy"]) and out["trade_opened"] and out["trade_closed"]
    return out


def test_payloads(now=None) -> tuple:
    """A TEST entry and its TEST close shaped like today's real ATLAS trade (SHORT 1 MNQ @ 26,380.75, target +$514): keys end in
    ':test' and are never recorded."""
    from . import push
    t = int(time.time() if now is None else now)
    e = push.entry_payload("TEST", "SHORT", 1, t, src="pc", entry=26380.75, stop=26419.5, target=26122.75)
    x = push.outcome_payload("TEST", "SHORT", "TARGET", 514.18, t, t + 60, src="pc", qty=1, R=6.6)
    for p, k in ((e, "fill"), (x, "out")):
        p.update(key=f"{k}:{t}:test", nm="TEST alert")
    return e, x


def ntfy_room(n_posts: int = TEST_NTFY_POSTS, now=None, base=None, http=None, work=None) -> tuple:
    """(room, why): whether n_posts more ntfy posts today still leave tools/pc_report.TRADE_ALERT_RESERVE for the trade alerts, by this
    PC's own count (pc_report.day_used: the report's posts + the instant alerts) AND ntfy's own count for this internet address
    (pc_report.ntfy_quota: a GET, not a message; every program on the PC is in it). Unknown = room. Never raises."""
    try:
        from tools import pc_report as R
        t = time.time() if now is None else float(now)
        used, cap = R.day_used(work or R.WORK_DEFAULT, t), R.NTFY_DAY_CAP - R.TRADE_ALERT_RESERVE
        if used + int(n_posts) > cap:
            return False, (f"this PC counted {used} of ntfy's {R.NTFY_DAY_CAP} posts today; the last {R.TRADE_ALERT_RESERVE} are "
                           "kept for trade alerts")
        q = R.ntfy_quota(base or R.NTFY_DEFAULT, http=http)
        if q and int(q.get("remaining") or 0) - int(n_posts) < R.TRADE_ALERT_RESERVE:
            return False, f"ntfy says {int(q.get('remaining') or 0)} posts left today; the last {R.TRADE_ALERT_RESERVE} are kept for trade alerts"
    except Exception:  # noqa: BLE001
        pass
    return True, ""


def send_test(now=None, sender=None, poster=None, ntfy_cfg=None, http=None, work=None, cooldown_s: float = TEST_COOLDOWN_S) -> dict:
    """One TEST entry + one TEST close to every Olympus phone AND to the private ntfy topic, now. -> {"app": {"sent", "devices",
    "errors", ...} of the entry, "app_close": ... of the close, "ntfy": "sent" or why not, "routes": routes(), "say": one plain line}.
    At most one test per cooldown_s ("cooldown": seconds to wait, nothing sent); the ntfy half is skipped when ntfy_room says no.
    sender / poster / ntfy_cfg / http (ntfy's quota GET) / work (the report's folder): tests. Never raises."""
    from . import notify, push
    out = {"app": {"sent": 0}, "app_close": {"sent": 0}, "ntfy": "not tried"}
    clock = time.time() if now is None else float(now)
    with _TEST_LOCK:
        last = _TEST["t"]
        if last is not None and cooldown_s and 0 <= clock - last < cooldown_s:
            wait = int(cooldown_s - (clock - last)) + 1
            out.update(cooldown=wait, app={"sent": 0, "skipped": "one test a minute"}, app_close={"sent": 0, "skipped": "one test a minute"},
                       ntfy="not tried (one test a minute)")
            out["routes"] = routes(ntfy_cfg)
            out["say"] = f"One test a minute: try again in {wait} s."
            return out
        _TEST["t"] = clock
    try:
        e, x = test_payloads(now)
        rows = []
        for p in (e, x):
            q = push.app_payload(p, now=now)
            q["body"] = f"{TEST_WORDS} {q.get('body') or ''}".strip()
            rows.append(push.app_send(q, sender=sender))
        out["app"], out["app_close"] = rows
        cfg = notify.alert_cfg() if ntfy_cfg is None else ntfy_cfg or {}
        room, why = (True, "") if not cfg.get("topic") else ntfy_room(TEST_NTFY_POSTS, now=now, base=cfg.get("ntfy"), http=http, work=work)
        if not cfg.get("topic"):
            out["ntfy"] = push.NO_TOPIC + " on this PC"
        elif not room:
            out["ntfy"] = "skipped: " + why
        else:
            ok = 0
            for p, mk in ((e, notify.entry_message), (x, notify.exit_message)):
                m = mk(p, now=now)
                m["body"] = f"{TEST_WORDS} {m['body']}"
                try:
                    good = bool((poster or notify._post)(cfg["ntfy"], cfg["topic"], m))
                except Exception as ex:  # noqa: BLE001
                    good, out["ntfy_error"] = False, ex.__class__.__name__
                if good:
                    ok += 1
                    notify.count_ntfy()              # today's real ntfy budget (now only shapes the words)
            out["ntfy"] = "sent" if ok == 2 else ("sent 1 of 2" if ok else "ntfy did not take it")
    except Exception as ex:  # noqa: BLE001
        out["error"] = ex.__class__.__name__
    out["routes"] = routes(ntfy_cfg)
    out["say"] = say(out)
    return out


def say(r: dict) -> str:
    """The PC dashboard's one-line answer to Send test (web/js/page-settings.js shows it as is): what each route answered."""
    a = r.get("app") or {}
    if a.get("sent"):
        app = f"Olympus: accepted for {a['sent']} phone(s), look at the iPhone"
    else:
        app = f"Olympus: not sent ({a.get('skipped') or ', '.join(a.get('errors') or []) or 'no phone took it'})"
    n = str(r.get("ntfy") or "not tried")
    return f"{app} · ntfy: {'TEST entry + close sent' if n == 'sent' else n}"


def describe(r: dict) -> list:
    """Plain lines for the console (no topic, no key, no id)."""
    lines = []
    if "app" in r:
        a = r.get("app") or {}
        if a.get("sent"):
            lines.append(f"[OK]  Olympus app: accepted for {a['sent']} phone(s). Accepted is not shown: look at the iPhone now.")
        else:
            lines.append(f"[..]  Olympus app: not sent ({a.get('skipped') or ', '.join(a.get('errors') or []) or 'no phone took it'})")
        n = str(r.get("ntfy"))
        lines.append("[OK]  ntfy: the TEST entry and close went to your private alert topic (the ntfy app shows them)" if n == "sent"
                     else f"[..]  ntfy: {n}")
    rt = r.get("routes") or r
    lines.append(f"      routes: {rt.get('phones', 0)} Olympus phone(s), ntfy topic {'set' if rt.get('ntfy') else 'NOT set'}; entries "
                 f"{'on' if rt.get('trade_opened') else 'OFF'}, results {'on' if rt.get('trade_closed') else 'OFF'}"
                 f"{', ring at night' if rt.get('ring_at_night') else ', silent at night (still shown)'}"
                 f"; routes {rt.get('trade_routes') or 'both'}")
    lines += [f"[FIX] {w}" if w.startswith("NO ROUTE") else f"[..]  {w}" for w in rt.get("warn") or []]
    return lines


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    r = send_test() if "--test" in argv else routes()
    for ln in describe(r):
        print("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
