"""Phone link for the bot server (owner 2026-11-20: "I want to add the account now on my phone, find a way").

The PC's Tailscale https address (https://<pc>.<tailnet>.ts.net/, port 443) can belong to another app on the PC (the owner's
old Jarvis app answered there with its own sign-in), so the bot pages (/add-account/, /safety/, /kalshi-live/) were not on the
phone link at all. At every server start this module makes sure the bot server has its OWN private https port inside the
owner's tailnet:

    https://<pc>.<tailnet>.ts.net:8444/  ->  http://127.0.0.1:8766  (tailnet only, never Funnel)

Rules: Windows PC only (os.name == "nt"), Tailscale installed and signed in, LE_PHONE_LINK != "0". It never touches port 443 or
any port another app uses, never turns Funnel on, and changes nothing when the bot server is already on a private port (any
port, e.g. LIVE_LINK.bat put it on 443). Runs once in a background thread at server start (never blocks the bot, every call
has a timeout). The pages themselves keep their own check (engine/live_site.private_why: tailnet devices only).
Tests: python -X utf8 -m tests.test_phone_link
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading

PORTS = (8444, 8446, 8448)                      # 443 = whatever the owner set (Jarvis / LIVE_LINK), 8443 = MONEY_INBOX
TARGETS = ("http://127.0.0.1:8766", "http://localhost:8766", "127.0.0.1:8766", "localhost:8766")
TIMEOUT = 20


def find_tailscale(env=None) -> str | None:
    env = os.environ if env is None else env
    p = env.get("LE_TAILSCALE")
    if p:
        return p if os.path.isfile(p) else None
    w = shutil.which("tailscale")
    if w:
        return w
    for d in (env.get("ProgramFiles"), env.get("ProgramFiles(x86)")):
        if d:
            c = os.path.join(d, "Tailscale", "tailscale.exe")
            if os.path.isfile(c):
                return c
    return None


def _run(ts, args, runner=None):
    runner = runner or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT))
    return runner([ts] + list(args))


def _json(ts, args, runner=None) -> dict:
    try:
        r = _run(ts, args, runner)
        out = (getattr(r, "stdout", "") or "").strip()
        return json.loads(out) if out else {}
    except Exception:  # noqa: BLE001
        return {}


def _ours(proxy) -> bool:
    p = str(proxy or "").strip().rstrip("/").lower()
    return any(p == t for t in TARGETS)


def scan(serve: dict) -> dict:
    """{'ours': [port...] (bot server, Funnel off), 'funnel': [port...] (bot server but Funnel on), 'used': {port...}}."""
    serve = serve if isinstance(serve, dict) else {}
    used = {int(k) for k in (serve.get("TCP") or {}) if str(k).isdigit()}
    funnel = {str(k).lower() for k, v in (serve.get("AllowFunnel") or {}).items() if v}
    ours, fun = [], []
    for hostport, web in (serve.get("Web") or {}).items():
        hp = str(hostport)
        port = int(hp.rsplit(":", 1)[1]) if ":" in hp and hp.rsplit(":", 1)[1].isdigit() else 443
        handlers = (web or {}).get("Handlers") or {}
        if any(_ours((h or {}).get("Proxy")) for h in handlers.values()):
            (fun if hp.lower() in funnel else ours).append(port)
        used.add(port)
    return {"ours": sorted(ours), "funnel": sorted(fun), "used": used}


def ensure(env=None, runner=None, ts=None, say=print) -> dict:
    """Make sure the bot server is on a private Tailscale https port. Returns {'ok', 'port', 'why'}. Never raises."""
    env = os.environ if env is None else env
    try:
        if str(env.get("LE_PHONE_LINK", "1")) == "0":
            return {"ok": False, "port": None, "why": "off (LE_PHONE_LINK=0)"}
        ts = ts or find_tailscale(env)
        if not ts:
            return {"ok": False, "port": None, "why": "Tailscale is not installed on this PC"}
        st = _json(ts, ["status", "--json"], runner)
        if str(st.get("BackendState", "")) != "Running":
            return {"ok": False, "port": None, "why": "Tailscale is not signed in / running"}
        s = scan(_json(ts, ["serve", "status", "--json"], runner))
        if s["ours"]:
            return {"ok": True, "port": s["ours"][0], "why": "already on"}
        port = next((p for p in PORTS if p not in s["used"]), None)
        if port is None:
            return {"ok": False, "port": None, "why": "no free port among %s" % (PORTS,)}
        _run(ts, ["serve", "--bg", "--yes", "--https=%d" % port, TARGETS[0]], runner)
        s2 = scan(_json(ts, ["serve", "status", "--json"], runner))
        if port in s2["ours"]:
            say("[phone_link] bot server on your private Tailscale link, port %d (tailnet only, Funnel off)" % port)
            return {"ok": True, "port": port, "why": "switched on"}
        return {"ok": False, "port": None, "why": "Tailscale did not take it (HTTPS certificates off in the tailnet?)"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "port": None, "why": "%s: %s" % (e.__class__.__name__, e)}


def start_background(env=None, say=print) -> threading.Thread | None:
    """Server start hook: Windows only, in a daemon thread, never blocks or breaks the bot."""
    env = os.environ if env is None else env
    if os.name != "nt" or str(env.get("LE_PHONE_LINK", "1")) == "0" or env.get("LE_CLOUD"):
        return None

    def _go():
        r = ensure(env=env, say=say)
        say("[phone_link] %s" % ("port %s: %s" % (r["port"], r["why"]) if r.get("ok") else "not on: " + str(r.get("why"))))

    t = threading.Thread(target=_go, name="phone_link", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print(ensure())
