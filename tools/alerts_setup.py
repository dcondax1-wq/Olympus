"""ALERTS_SETUP.bat / tools/bat/TEST_ALERT.bat / tools/bat/ALERTS_OFF.bat / tools/bat/ALERTS_ON.bat (engine/alert_bus.py). Stdlib only.

  python -X utf8 tools/alerts_setup.py setup     asks 1 Telegram, 2 Discord, 3 both; the token / webhook is pasted HIDDEN (getpass)
  python -X utf8 tools/alerts_setup.py test      a fake "TEST: Zlarior 50K LONG opened ..." through EVERY channel, with receipts
  python -X utf8 tools/alerts_setup.py off|on    the bus off (old ntfy + Web Push path, exactly) / back on
  python -X utf8 tools/alerts_setup.py status    what is set up (never the secrets)

Saved ONLY in %USERPROFILE%\\.olympus\\alerts.json (never the repo). Secrets are never printed: every line goes through
alert_bus.redact. The bot never reads messages sent TO it: getUpdates runs only here, once, to learn your chat id.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import alert_bus as AB  # noqa: E402

WAIT_S = 180                   # up to 3 minutes for your /start


def cfg_path(env=None) -> str:
    return os.path.join(AB.home(env), AB.CFG_NAME)


def load_raw(env=None) -> dict:
    try:
        with open(cfg_path(env), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_raw(d: dict, env=None) -> str:
    p = cfg_path(env)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def wait_chat_id(token: str, say=print, wait_s: int = WAIT_S, sleep=time.sleep, clock=time.time, code: str | None = None) -> str | None:
    """Poll getUpdates until someone sends /start to the bot; their chat id. Clears the read updates (offset) so nothing
    stays queued. Only a private chat counts. code (day-security3 2026-11-21, the /alerts/ page): only "/start <code>" counts,
    the message Telegram sends when the owner opens https://t.me/<bot>?start=<code> from the page; a stranger who finds the new
    bot in those 3 minutes and taps START (a plain "/start") is ignored, so the alerts can never go to his chat."""
    end, offset = clock() + wait_s, None
    while clock() < end:
        url = f"{AB.TG_API}/bot{token}/getUpdates?timeout=20" + (f"&offset={offset}" if offset else "")
        st, txt = AB._http("GET", url, None, {}, 30)
        j = AB._json(txt)
        if st == 401:
            say("Telegram says that token is wrong. Copy it again from BotFather.")
            return None
        for u in j.get("result") or []:
            offset = int(u.get("update_id") or 0) + 1
            msg = AB._d(u.get("message"))
            chat = AB._d(msg.get("chat"))
            said = str(msg.get("text") or "").strip()
            ok_start = said == f"/start {code}" if code else said.lower().startswith("/start")
            if chat.get("type") == "private" and ok_start:
                AB._http("GET", f"{AB.TG_API}/bot{token}/getUpdates?offset={offset}&timeout=0", None, {}, 15)
                return str(chat.get("id"))
        if st != 200:
            sleep(3)
    return None


def setup_telegram(raw: dict, ask=getpass.getpass, say=print, wait=wait_chat_id) -> bool:
    say("TELEGRAM. On your iPhone: Telegram -> search @BotFather -> /newbot -> a name -> a username ending in 'bot'.")
    say("BotFather answers with a token. Paste it here (it stays hidden as you type) and press Enter:")
    token = (ask("Bot token (hidden): ") or "").strip()
    if not AB.good_token(token):
        say("That does not look like a BotFather token (numbers, a colon, then letters). Nothing saved.")
        return False
    say("Now on your iPhone open your new bot (the link BotFather gave you) and tap START. Waiting up to 3 minutes ...")
    chat = wait(token, say=say)
    if not chat:
        say("No /start seen in 3 minutes. Run ALERTS_SETUP again and tap START in your bot.")
        return False
    raw["telegram"] = {"token": token, "chat_id": chat, "on": True}
    rid, why = AB.send_telegram(raw["telegram"], "Olympus alerts are ON", "This chat now gets your trade alerts. Messages you send "
                                "here are ignored.", False)
    say("Telegram test: " + (f"delivered ({AB.redact(rid, AB.config())})" if rid else AB.redact(why, {"telegram": raw["telegram"]})))
    return bool(rid)


def setup_discord(raw: dict, ask=getpass.getpass, say=print) -> bool:
    say("DISCORD. In Discord: your server -> a channel -> Edit Channel (gear) -> Integrations -> Webhooks -> New Webhook -> Copy Webhook URL.")
    say("Paste it here (it stays hidden as you type) and press Enter:")
    hook = (ask("Webhook URL (hidden): ") or "").strip()
    if not AB.good_webhook(hook):
        say("That does not look like a Discord webhook URL (https://discord.com/api/webhooks/...). Nothing saved.")
        return False
    raw["discord"] = {"webhook": hook, "on": True}
    rid, why = AB.send_discord(raw["discord"], "Olympus alerts are ON", "This channel now gets your trade alerts.", False)
    say("Discord test: " + (f"delivered ({rid})" if rid else AB.redact(why, {"discord": raw["discord"]})))
    return bool(rid)


def setup(ask_choice=input, ask=getpass.getpass, say=print, env=None, wait=wait_chat_id) -> int:
    say("OLYMPUS ALERTS SETUP: where should your trade alerts go?")
    say("  1 = Telegram (recommended)   2 = Discord   3 = both")
    c = (ask_choice("Type 1, 2 or 3 and press Enter: ") or "").strip()
    if c not in ("1", "2", "3"):
        say("Nothing changed.")
        return 1
    raw = load_raw(env)
    ok = []
    if c in ("1", "3"):
        ok.append(setup_telegram(raw, ask=ask, say=say, wait=wait))
    if c in ("2", "3"):
        ok.append(setup_discord(raw, ask=ask, say=say))
    if any(ok):
        save_raw(raw, env)
        say("Saved in %USERPROFILE%\\.olympus\\alerts.json (never the bot folder, never GitHub).")
        say("Done. The bot's alerts now go here first; ntfy and the Olympus app stay as backups. TEST_ALERT checks every channel.")
        return 0
    say("Nothing saved.")
    return 1


def test(say=print, cfg=None) -> int:
    cfg = cfg if cfg is not None else AB.config()
    say(f"TEST ALERT: {AB.TEST_TITLE}")
    if AB.switched_off():
        say("Note: the alert bus is switched OFF (ALERTS_ON turns it back on); this test still tries every channel.")
    res = AB.test_all(cfg)
    good = 0
    for ch, (rid, why) in res.items():
        if rid:
            good += 1
            say(f"  OK    {AB.NAMES[ch]:<16} receipt {AB.redact(rid, cfg)}")
        else:
            say(f"  FAIL  {AB.NAMES[ch]:<16} {AB.redact(why, cfg)}")
    if not cfg.get("telegram") and not cfg.get("discord"):
        say("  (no Telegram / Discord yet: run ALERTS_SETUP)")
    say(f"{good} of {len(res)} channels delivered.")
    return 0 if good else 1


def switch(on: bool, say=print, env=None) -> int:
    p = os.path.join(AB.home(env), AB.OFF_NAME)
    if on:
        if os.path.exists(p):
            os.remove(p)
        say("Alert bus ON: Telegram / Discord first, ntfy and the Olympus app as backups." if AB.active(env) else
            "Alert bus ON, but no Telegram / Discord is set up yet: run ALERTS_SETUP. Until then the old ntfy + app path runs.")
    else:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("alert bus off: the old ntfy + Web Push path runs exactly as before. tools/bat/ALERTS_ON.bat removes this file.\n")
        say("Alert bus OFF: alerts take the old path (ntfy private topic + the Olympus app), exactly as before.")
    return 0


def status(say=print) -> int:
    c = AB.config()
    say(f"Telegram: {'set up' if c.get('telegram') else 'not set up'}; Discord: {'set up' if c.get('discord') else 'not set up'}; "
        f"bus: {'ON' if AB.active(cfg=c) else 'OFF (old path)'}")
    return 0


def main(argv=None) -> int:
    a = (argv if argv is not None else sys.argv[1:]) or ["status"]
    cmd = a[0]
    if cmd == "setup":
        r = setup()
        if r == 0:
            test()
        return r
    if cmd == "test":
        return test()
    if cmd in ("off", "on"):
        return switch(cmd == "on")
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
