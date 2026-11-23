"""One loud line for a file the bot could not read (night-faults 2026-11-23).

A corrupt data/accounts.json, data/rapid.json or data/account_b.json used to read as "no such account": that account simply
stopped trading with no word (the readers return their safe default, which is right: an unreadable account is never armed).
corrupt() keeps that safe default and adds the word: a log line (once a day per file: the readers run every poll), logs/faults.json (the last problem per file),
and ONE private problem push a day per file (engine/notify.instant_problem, in a daemon thread: the internet being down
never blocks). Only files under this bot's data/ folder push; a test's temp file only logs. Never raises.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LOG = os.path.join(ROOT, "logs", "faults.json")
PUSH = None          # tests: fn(problem dict) instead of the phone
_SEEN: dict = {}
_LOCK = threading.Lock()


def _real(path) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), DATA]) == DATA
    except Exception:
        return False


def corrupt(path, err, what: str = "", now=None) -> dict:
    """Record that `path` exists but could not be read. `what` = what stops because of it ("the extra accounts do not
    trade"). Returns the problem dict (tests). Never raises."""
    try:
        now = time.time() if now is None else float(now)
        name = os.path.basename(str(path))
        text = f"{name} is unreadable ({err.__class__.__name__}: {str(err)[:100]})" + (f": {what}" if what else "")
        day = time.strftime("%Y-%m-%d", time.localtime(now))
        p = {"key": f"corrupt:{name}:{day}", "code": "bot_down", "title": f"{name} is unreadable",
             "body": f"{text}. Fix: restore it from a backup or re-run its setup (ADD_ACCOUNT.bat / START BOT); "
                     f"send Claude a photo if unsure."}
        real = _real(path)
        with _LOCK:
            first = _SEEN.get(p["key"]) is None
            _SEEN[p["key"]] = now
        if not first:
            return p                             # read every poll: said once a day, not every poll
        print(f"[fault] {text}", file=sys.stderr, flush=True)
        if real:
            try:
                os.makedirs(os.path.dirname(LOG), exist_ok=True)
                try:
                    with open(LOG, encoding="utf-8") as fh:
                        cur = json.load(fh)
                    cur = cur if isinstance(cur, dict) else {}
                except Exception:
                    cur = {}
                cur[name] = {"t": int(now), "text": text}
                with open(LOG + ".tmp", "w", encoding="utf-8") as fh:
                    json.dump(cur, fh, indent=1)
                os.replace(LOG + ".tmp", LOG)
            except Exception:
                pass
        if first and (real or PUSH is not None):
            fn = PUSH

            def go():
                try:
                    if fn is not None:
                        fn(p)
                    else:
                        from . import notify
                        notify.instant_problem(p)
                except Exception:
                    pass
            if fn is not None:
                go()
            else:
                threading.Thread(target=go, name="fault-push", daemon=True).start()
        return p
    except Exception:
        return {}
