"""Every critical phone event -> who sends it, on which channel, with ZERO owner setup (night-notify 2026-11-22, owner: "get
notifications going on your own": the phone must buzz for every important event with the fewest owner steps).

  python -X utf8 -m engine.alert_map          the table, plain words (what / sender / zero-setup channels / setting)

Zero setup = no Telegram, no Discord, no repo secret: the private ntfy topic (made by the 15-minute report once per PC,
tools/pc_report.ensure_topic) and the installed Olympus app (Web Push, the "Allow notifications" tap). Telegram / Discord, when
set up, go first (engine/alert_bus). tests/test_alert_map.py checks every row: its senders import, its notify_settings.json
type is ON, its channels are private ones only (never the public status topic), and its key prefix maps to that type.
Read-only: nothing here sends, places or arms anything.
"""
from __future__ import annotations

import importlib

PRIVATE = ("ntfy", "webpush", "telegram", "discord")      # the channels an alert may use (the public status topic is NOT one)
BOTH = ("ntfy", "webpush")

# id, what (plain words), senders ("module:function", the first is the main one), zero-setup channels, notify_settings.json type,
# key prefix (engine/notify.kind_of / alert_bus keys), critical (buzz at once) or digest (once a day, no buzz)
EVENTS = (
    {"id": "bot_stopped", "what": "Bot stopped or crashed in trading hours",
     "senders": ("engine.fast_alarm:evaluate", "engine.notify:instant_problem", "tools.pc_report:run_once"),
     "zero": BOTH, "type": "problems", "key": "cond:bot_down", "critical": True},
    {"id": "not_armed", "what": "An account is NOT armed 90 s after START (or at the 17:30 / 01:15 / 08:45 checks)",
     "senders": ("engine.readiness:tick", "engine.readiness:send_alert"),
     "zero": BOTH, "type": "problems", "key": "ready:no:", "critical": True},
    {"id": "entry_blocked", "what": "Entries blocked: PC clock off, feed stale, NinjaTrader not connected, kill switch",
     "senders": ("engine.readiness:send_alert", "engine.fast_alarm:evaluate"),
     "zero": BOTH, "type": "problems", "key": "cond:feed_stale", "critical": True},
    {"id": "trade_entry", "what": "Trade entry with $ risk and $ at target, per account",
     "senders": ("engine.push:pc_notify", "engine.notify:instant_entry"),
     "zero": BOTH, "type": "trade_opened", "key": "open:", "critical": True},
    {"id": "trade_exit", "what": "Trade exit with $ result, today's $ and $ to pass, per account",
     "senders": ("engine.push:pc_notify", "engine.notify:instant_exit"),
     "zero": BOTH, "type": "trade_closed", "key": "close:", "critical": True},
    {"id": "dll_near", "what": "Daily loss limit near (70% used today)",
     "senders": ("tools.pc_guard:account_pushes", "tools.pc_report:run_once"),
     "zero": BOTH, "type": "room_low", "key": "guard:dll:", "critical": True},
    {"id": "breach_risk", "what": "Breach risk: 50 / 75% of max drawdown used, an open trade into a halt, a trade with no stop",
     "senders": ("tools.pc_guard:account_pushes", "engine.fast_alarm:evaluate"),
     "zero": BOTH, "type": "room_low", "key": "guard:dd:", "critical": True},
    {"id": "payout_ready", "what": "Payout can be requested: after the close, $ + the MFFU clicks (and PASSED / FAILED / LOCKED)",
     "senders": ("engine.payout_autopilot:tick", "engine.lifecycle:detect", "tools.pc_report:run_once"),
     "zero": BOTH, "type": "account_status", "key": "payout:", "critical": True},
    {"id": "payout5_guard", "what": "Builder payout #4 taken: do NOT take payout #5 (live move, every sim sleeps)",
     "senders": ("engine.payout_autopilot:alerts", "engine.funded_life:track"),
     "zero": BOTH, "type": "account_status", "key": "payout5:", "critical": True},
    {"id": "rapid_live_day", "what": "A Rapid day near MFFU's $10,000 live line ($6,000+ net)",
     "senders": ("engine.payout_autopilot:alerts", "engine.rapid:status"),
     "zero": BOTH, "type": "problems", "key": "rapid10k:", "critical": True},
    {"id": "keepalive_deadline", "what": "MFFU 7-day no-trade deadline coming (day 5+)",
     "senders": ("tools.pc_guard:quiet_push", "engine.readiness:send_alert"),
     "zero": BOTH, "type": "account_status", "key": "guard:quiet:", "critical": True},
    {"id": "pc_silent", "what": "PC silent (the cloud sees no report for 20 min in market hours)",
     "senders": ("tools.pc_silent_check:run",),
     "zero": (), "type": "pc_silent", "key": "pc_silent:", "critical": True,
     "gap": "the cloud cannot know the PC's private topic: it needs ONE repo secret (LE_NTFY_TOPIC = the topic, or "
            "LE_TG_TOKEN + LE_TG_CHAT); without it the plain alert goes to the public status topic only"},
    {"id": "update_failed", "what": "Update failed or rolled back (the PC stays on the old code)",
     "senders": ("engine.autoupdate:alert_for", "engine.autoupdate:notify"),
     "zero": BOTH, "type": "problems", "key": "auto:update:", "critical": True},
    {"id": "update_applied", "what": "Update applied / skipped (low priority)",
     "senders": ("engine.autoupdate:alert_for", "engine.alert_bus:digest_add"),
     "zero": BOTH, "type": "daily_summary", "key": "digest:", "critical": False},
)


def resolve(sender: str):
    """'module:function' -> the function (raises when it is gone: the test catches a renamed sender)."""
    mod, _, fn = sender.partition(":")
    return getattr(importlib.import_module(mod), fn)


def coverage(settings=None) -> list:
    """[{id, what, ok, why, zero, type_on}] for every event. Never raises."""
    try:
        from . import notify
        s = settings or notify.settings()
    except Exception:
        notify, s = None, {}
    out = []
    for e in EVENTS:
        why = []
        for sd in e["senders"]:
            try:
                if not callable(resolve(sd)):
                    why.append(f"{sd} is not a function")
            except Exception as ex:  # noqa: BLE001
                why.append(f"{sd} missing ({ex.__class__.__name__})")
        on = bool(notify and notify.on(e["type"], s))
        if not on:
            why.append(f"notify_settings.json '{e['type']}' is OFF")
        bad = [c for c in e["zero"] if c not in PRIVATE]
        if bad:
            why.append(f"not a private channel: {bad}")
        out.append({"id": e["id"], "what": e["what"], "ok": not why, "why": "; ".join(why), "zero": list(e["zero"]),
                    "type_on": on, "critical": e["critical"], "gap": e.get("gap", "")})
    return out


NAMES = {"ntfy": "ntfy app", "webpush": "Olympus app"}


def table() -> str:
    rows = ["| Event | Zero-setup phone route | OK |", "|---|---|---|"]
    for r in coverage():
        ch = " + ".join(NAMES.get(c, c) for c in r["zero"]) or ("needs 1 secret: " + r["gap"].split(":")[0] if r["gap"] else "none")
        rows.append(f"| {r['what']} | {ch}{'' if r['critical'] else ' (daily digest, no buzz)'} | "
                    f"{'OK' if r['ok'] else 'FIX: ' + r['why']} |")
    return "\n".join(rows)


if __name__ == "__main__":
    print(table())
