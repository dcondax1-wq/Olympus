"""SEND ME A TEST ALERT from the cloud (day-notify 2026-11-23, owner: "proof that notifications ACTUALLY arrive on my iPhone").

One tap on the phone (GitHub app or github.com -> Actions -> "Send me a test alert" -> Run workflow; the workflow file is the lead's,
research/handoff/2026-11-23/day-notify/LEAD_WIRES.md) runs this script on GitHub's free runner. The PC can be OFF: this is exactly the
route a real cloud critical alert takes ("Your PC stopped reporting", tools/pc_silent_check.py):

  1. Telegram / Discord   when the repo secrets LE_TG_TOKEN + LE_TG_CHAT / LE_DISCORD_WEBHOOK hold them (engine/alert_bus.deliver)
  2. the private ntfy topic when the repo secret LE_NTFY_TOPIC holds it (the topic the owner's ntfy app follows); without it the
     message goes to the PUBLIC status topic, like a real PC-silent alert, and the receipt says the phone most likely did not get it

Every channel that is set up gets the test (a real alert stops at the first one that answers; a test checks them all).
Title: "TEST: Olympus alerts work 4:05 PM ET".

DELIVERY RECEIPT: ntfy = the message is READ BACK from the topic by its id (proof ntfy holds it for the phone); Telegram / Discord =
the message id their API returned. The receipt (ok / failed per channel, no topic, no token, no chat id) is then posted to the
public status topic as {"kind": "le-alert-test", ...} (every page / board reader filters by kind, so nothing else sees it), printed
in the job log and the run's summary, and the job goes RED when no owner channel took the test (green check = it worked).

What it can NOT reach: the Olympus app (Web Push). The app's subscription is sealed to the PC's key (engine/push), so only the PC can
push to it; the app's own "Send a test" button tests that route (the PC answers within 5 minutes).

  python tools/alert_test.py --out pcw            send the test + the receipt (the workflow step)
  python tools/alert_test.py --dry-run            print what it would send, send nothing
  python tools/alert_test.py --last               print the newest receipt from the public status topic (Claude / the lead)
Stdlib only. Never places, changes or arms anything. Tests: python -X utf8 -m tests.test_alert_test (fake transports only).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import pc_silent_check as PS  # noqa: E402

KIND = "le-alert-test"
TITLE = "TEST: Olympus alerts work"
BODY = ("Sent from GitHub (the cloud), not your PC: the same way a real 'PC stopped reporting' alert reaches you. "
        "If you see this, cloud alerts work. Nothing to do.")
READ_BACK_S = (2, 5, 10)            # wait, then read the topic back (ntfy usually shows a message within a second)
OUT_NAME = "alert_test.json"
OWNER = ("telegram", "discord", "ntfy")


def hm(t) -> str:
    try:
        from engine import notify
        return notify._et(t).strftime("%I:%M %p ET").lstrip("0")
    except Exception:
        return time.strftime("%H:%M UTC", time.gmtime(t))


def _post_json(txt) -> dict:
    try:
        j = json.loads(txt or "")
        return j if isinstance(j, dict) else {}
    except Exception:
        return {}


def read_back(base, topic, mid, title, get=None, sleep=time.sleep, waits=READ_BACK_S) -> bool:
    """True when the topic holds the message (by ntfy's id, else by its exact title). Never raises."""
    try:
        for w in waits:
            sleep(w)
            ok, msgs = PS.poll(base, topic, since="15m", get=get)
            if ok and any((mid and m.get("id") == mid) or (not mid and m.get("title") == title) for m in msgs):
                return True
        return False
    except Exception:
        return False


def send_ntfy(d, title, body, post, get, sleep) -> str:
    """'ok' (posted + read back) | 'posted, not read back' | 'failed (HTTP n)'."""
    h = {"Content-Type": "text/plain; charset=utf-8", "Title": title, "Priority": "high", "Tags": "white_check_mark,test_tube"}
    code, txt = post(f"{d['base']}/{d['topic']}", body.encode("utf-8"), h)
    if not 200 <= int(code or 0) < 300:
        return f"failed (HTTP {code or 'no answer'})"
    return "ok" if read_back(d["base"], d["topic"], _post_json(txt).get("id"), title, get=get, sleep=sleep) else "posted, not read back"


def send_bus(bus, env, title, body, tmp) -> dict:
    """Telegram / Discord through engine/alert_bus.deliver, each channel on its own (a test checks all). -> {channel: words}."""
    out = {}
    cfg = PS._bus_cfg(bus, env)
    for ch in ("telegram", "discord"):
        if not cfg.get(ch):
            out[ch] = "not set up"
            continue
        try:
            r = bus.deliver({"kind": "test", "key": "", "title": title, "body": body, "only": [ch], "backoff": (5,), "no_record": True},
                            cfg=cfg, path=os.path.join(tmp, "alert_bus_sent.json"), log_path=os.path.join(tmp, "alert_bus.jsonl"))
            out[ch] = "ok" if ch in (r.get("receipts") or {}) else f"failed ({bus.redact(str((r.get('failed') or {}).get(ch) or 'no receipt'), cfg)[:80]})"
        except Exception as e:  # noqa: BLE001
            out[ch] = f"failed ({e.__class__.__name__})"
    return out


def run(out="pcw", now=None, env=None, get=None, post=None, bus="auto", sleep=time.sleep, say=print, feed=None, dry=False,
        publish=True) -> dict:
    """One test through every cloud channel + the receipt. -> {"ok", "ch" {channel: words}, "to", "title", ...}. Never raises."""
    env = os.environ if env is None else env
    now = int(now or time.time())
    get, post = get or PS.http_get, post or PS.http_post
    feed = feed or PS.feed_cfg()
    title = f"{TITLE} {hm(now)}"
    d = PS.dest(env, feed)
    res = {"kind": KIND, "v": 1, "t": now, "title": title, "to": "private" if d["private"] else ("status topic" if d["topic"] else "none"),
           "ch": {}, "ok": False}
    try:
        if bus == "auto":
            bus = PS._bus(env)
        tmp = env.get("RUNNER_TEMP") or out
        if dry:
            say(f"[dry] {title}: {BODY}")
            say(f"[dry] to: ntfy {res['to']}" + (", Telegram / Discord (alert bus)" if bus else ""))
            res["ch"] = {"ntfy": "dry run"}
            return res
        if bus is not None:
            res["ch"].update(send_bus(bus, env, title, BODY, tmp))
        else:
            res["ch"].update(telegram="not set up", discord="not set up")
        if d["topic"]:
            res["ch"]["ntfy"] = send_ntfy(d, title, BODY, post, get, sleep)
        else:
            res["ch"]["ntfy"] = "no topic"
        owner = [c for c in OWNER if res["ch"].get(c) == "ok" and (c != "ntfy" or d["private"])]
        res["ok"] = bool(owner)
        res["via"] = owner
        if res["ch"].get("ntfy") == "ok" and not d["private"]:
            res["note"] = "only on the PUBLIC status topic: add the repo secret LE_NTFY_TOPIC (your private topic) so it reaches you"
        elif not owner:
            res["note"] = "no channel you follow took the test"
    except Exception as e:  # noqa: BLE001
        res["error"] = e.__class__.__name__
    receipt = {k: res[k] for k in ("kind", "v", "t", "ok", "ch", "to") if k in res}
    if publish and feed.get("topic"):            # the receipt goes to the PUBLIC status topic: words only, no topic / token / id
        code, _ = post(f"{feed['ntfy']}/{feed['topic']}", json.dumps(receipt, separators=(",", ":")).encode("utf-8"),
                       {"Content-Type": "application/json", "Title": "Alert test receipt", "Priority": "min", "Tags": "receipt"})
        res["receipt_posted"] = 200 <= int(code or 0) < 300
    try:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, OUT_NAME), "w", encoding="utf-8") as fh:
            json.dump(receipt, fh, separators=(",", ":"))
    except OSError:
        pass
    for ln in lines(res):
        say(ln)
    summary = env.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("\n".join(["### " + title, "", "| channel | result |", "|---|---|"]
                                   + [f"| {c} | {w} |" for c, w in res["ch"].items()]
                                   + ["", "**" + ("WORKED" if res["ok"] else "DID NOT REACH YOU") + "**"
                                      + (f": {res['note']}" if res.get("note") else ""), ""]))
        except OSError:
            pass
    return res


def lines(res) -> list:
    out = [f"alert test {res.get('title')}: " + ("WORKED" if res.get("ok") else "DID NOT REACH YOU")]
    for c, w in (res.get("ch") or {}).items():
        out.append(f"  {c:9} {w}" + (" (private topic)" if c == "ntfy" and res.get("to") == "private" and w == "ok" else ""))
    if res.get("note"):
        out.append("  -> " + res["note"])
    return out


def last(get=None, feed=None) -> dict | None:
    """The newest receipt on the public status topic (ntfy keeps 12 h), or None."""
    feed = feed or PS.feed_cfg()
    ok, msgs = PS.poll(feed["ntfy"], feed["topic"], since="12h", get=get)
    best = None
    for m in msgs:
        j = _post_json(m.get("message"))
        if j.get("kind") == KIND and (best is None or int(j.get("t") or 0) > int(best.get("t") or 0)):
            best = j
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cloud: send ONE test alert through every cloud channel, read it back, post the receipt.")
    ap.add_argument("--out", default="pcw")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--last", action="store_true")
    a = ap.parse_args(argv)
    if a.last:
        r = last()
        if not r:
            print("no alert test receipt in the last 12 h")
            return 0
        print(f"last alert test {hm(r.get('t') or 0)}: {'WORKED' if r.get('ok') else 'DID NOT REACH YOU'} (ntfy to {r.get('to')})")
        for c, w in (r.get("ch") or {}).items():
            print(f"  {c:9} {w}")
        return 0
    try:
        r = run(a.out, dry=a.dry_run)
    except Exception as e:  # noqa: BLE001
        print(f"alert test failed ({e.__class__.__name__})")
        return 1
    return 0 if (r.get("ok") or a.dry_run) else 1


if __name__ == "__main__":
    sys.exit(main())
