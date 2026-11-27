"""Phone alerts: Telegram bot and/or Discord webhook (off by default since 2026-10-18: the owner gets notifications through
the phone app, engine/push.py). Chat alerts send only when LE_ALERTS_CHAT=1 or live_model.json {"alerts": {"chat": true}}.
System alerts (server restart / resume failures) also go to the app as a notification.

Config lives only on this machine in data/alerts.json (you enter it in Settings). Secrets are never returned to the
browser in full. Telegram: create a bot with @BotFather -> token; message the bot once, then use @userinfobot (or the
getUpdates API) for your chat id. Discord: Server Settings -> Integrations -> Webhooks -> New Webhook -> Copy URL.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "alerts.json")
EVENTS = {"sweep": False, "signal": True, "entry": True, "exit": True, "guard": True, "daily": True, "regime": True}
_lock = threading.Lock()
_recent: list = []


def load() -> dict:
    cfg = {"telegram_token": "", "telegram_chat": "", "discord_webhook": "", "events": dict(EVENTS)}
    if os.path.exists(PATH):
        try:
            saved = json.load(open(PATH, encoding="utf-8"))
            cfg.update({k: v for k, v in saved.items() if k != "events"})
            cfg["events"].update(saved.get("events", {}))
        except Exception:
            pass
    return cfg


def save(patch: dict) -> dict:
    cfg = load()
    for k in ("telegram_token", "telegram_chat", "discord_webhook"):
        v = patch.get(k)
        if v is not None and not str(v).startswith("•"):      # masked values coming back from the UI are ignored
            cfg[k] = str(v).strip()
    if isinstance(patch.get("events"), dict):
        cfg["events"].update({k: bool(v) for k, v in patch["events"].items() if k in EVENTS})
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(cfg, open(PATH, "w", encoding="utf-8"), indent=2)
    return public(cfg)


def _mask(s):
    return "" if not s else "•" * 6 + s[-4:]


def public(cfg=None) -> dict:
    cfg = cfg or load()
    return {"telegram_token": _mask(cfg["telegram_token"]), "telegram_chat": cfg["telegram_chat"],
            "discord_webhook": _mask(cfg["discord_webhook"]), "events": cfg["events"],
            "telegram_on": bool(cfg["telegram_token"] and cfg["telegram_chat"]), "discord_on": bool(cfg["discord_webhook"]),
            "chat_on": chat_on(),
            "recent": _recent[-20:]}


def _post(url, body):
    from . import pc_identity                        # day-noleak
    if not pc_identity.may_post("alert", url=url):
        return 0
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "LiquidityEngine/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def chat_on() -> bool:
    """Telegram / Discord switch: env LE_ALERTS_CHAT=1 or live_model.json {"alerts": {"chat": true}} (default off)."""
    if os.environ.get("LE_ALERTS_CHAT", "") == "1":
        return True
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "live_model.json"), encoding="utf-8") as fh:
            return bool((json.load(fh).get("alerts") or {}).get("chat"))
    except Exception:
        return False


def _push_system(text: str, kind: str):
    """Server-level alerts (autostart resume failures, restarts) also reach the phone app. Never raises."""
    if kind != "system":
        return
    try:
        from . import push
        first, _, rest = str(text).partition(". ")
        push.pc_notify(push.text_payload("PC", "system", first[:90], rest or first, key=f"system:{int(time.time()) // 60}:{abs(hash(text)) % 10**6}"))
    except Exception:
        pass


def _short(text: str, kind: str) -> str:
    """day-tgpretty: the short emoji Telegram text (engine/tg_pretty; LE_TG_PRETTY=0 or any trouble: the text as it was)."""
    try:
        if str(os.environ.get("LE_TG_PRETTY", "1")).strip() == "0":
            return text
        from . import tg_pretty
        first, _, rest = str(text).partition(". ")
        return tg_pretty.fmt({"kind": "report", "key": f"{kind}:", "notify_type": "problems" if kind in ("error", "system") else kind},
                             first, rest)
    except Exception:
        return text


def send(text: str, kind: str = "signal", force: bool = False) -> dict:
    """Send to every configured channel when this kind of alert is enabled and chat alerts are switched on. Never raises."""
    _push_system(text, kind)
    if not chat_on():
        return {"sent": False, "reason": "Telegram / Discord are off (the phone app notifies; LE_ALERTS_CHAT=1 turns them on)"}
    cfg = load()
    if not force and not cfg["events"].get(kind, False):
        return {"sent": False, "reason": f"{kind} alerts are off"}
    res = {}
    if cfg["telegram_token"] and cfg["telegram_chat"]:
        try:
            res["telegram"] = _post(f"https://api.telegram.org/bot{cfg['telegram_token']}/sendMessage",
                                    {"chat_id": cfg["telegram_chat"], "text": _short(text, kind), "disable_web_page_preview": True})
        except Exception as e:
            res["telegram"] = f"error: {e.__class__.__name__}"
    if cfg["discord_webhook"]:
        try:
            res["discord"] = _post(cfg["discord_webhook"], {"content": text[:1900]})
        except Exception as e:
            res["discord"] = f"error: {e.__class__.__name__}"
    with _lock:
        _recent.append({"t": int(time.time()), "kind": kind, "text": text[:200], "result": res})
        del _recent[:-50]
    return {"sent": bool(res), "result": res}
