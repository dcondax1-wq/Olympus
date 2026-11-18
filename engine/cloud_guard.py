"""Cloud guard: what changes when the dashboard runs on an always-on server (reachable with your PC off).

LE_DASH_PASSWORD   set -> every page and /api call needs it (the browser shows a login box; any username works).
                   Open without it: /api/health/ping (host health checks) and /api/tv/webhook (it has its own key).
LE_CLOUD=1         paper only. Refuses live arming / go-live / outbound webhook tests and any non-paper adapter.
                   Live orders on the eval go TradingView -> bridge (TradersPost / PickMyTrade), never through here.
                   LE_CLOUD=1 without LE_DASH_PASSWORD refuses to start: no open dashboard on the internet.

Local use is unchanged when neither variable is set.
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import os

from fastapi.responses import JSONResponse, Response

OPEN_PATHS = ("/api/health/ping", "/api/tv/webhook")
# the Start page's arm / start / account writes (engine/start_api.py): also refused off this PC by local_only() below
START_WRITES = ("/api/next/start/names", "/api/next/start/nt", "/api/next/start/setup", "/api/next/start/sims",
                "/api/next/start/arm", "/api/next/start/go", "/api/next/start/resume", "/api/next/start/clock",
                "/api/next/start/accounts/add", "/api/next/start/accounts/remove",
                "/api/next/start/accounts/anchor", "/api/next/start/accounts/funded", "/api/next/start/newacct",
                "/api/next/start/onboard", "/api/next/start/rearm",          # one-tap accounts + Re-arm now (engine/onboard.py)
                "/api/next/start/blitz", "/api/next/start/blitz/arm",          # BLITZ's own 25K (account C, engine/account_c.py)
                "/api/next/start/selftest")                                    # "Run self-test" (engine/pc_selftest.py)
# the Goals page's money form (engine/money_api.py: the owner's savings / jobs / Kalshi figures): PC only as well
MONEY_WRITES = ("/api/next/money",)
# the Fleet page's buttons (engine/fleet_api.py: data/fleet.json add / remove / on / off / kill / funded / payout; never arms)
FLEET_WRITES = ("/api/next/fleet/set",)
CLOUD_BLOCKED = ("/api/live/arm", "/api/live/golive", "/api/launch/test_webhook", *START_WRITES, *MONEY_WRITES, *FLEET_WRITES)
LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1")
PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-real-ip", "forwarded", "cf-connecting-ip", "true-client-ip",
                 "tailscale-user-login", "x-original-forwarded-for")


def _hostname(v: str) -> str:
    v = (v or "").strip().lower()
    if "://" in v:
        v = v.split("://", 1)[1]
    v = v.split("/", 1)[0]
    if v.startswith("["):
        return v[1:].split("]", 1)[0]
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


def local_only(request) -> str | None:
    """Why this request may not arm, start or change accounts (None = it comes from a browser on this PC). Refused: cloud
    mode, a caller that is not this PC (the phone on the LAN / Tailscale), anything relayed by a proxy or tunnel, a Host
    or Origin that is not localhost (a web page on another site, DNS rebinding)."""
    if os.environ.get("LE_CLOUD") == "1":
        return "cloud mode is paper only: arming and account changes are done on the PC itself"
    client = getattr(getattr(request, "client", None), "host", None) or ""
    if client not in LOCAL_HOSTS:
        return "only on the PC itself (http://localhost:8766): the phone and other computers can only look"
    if any(request.headers.get(h) for h in PROXY_HEADERS):
        return "only on the PC itself: this request came through a proxy or tunnel"
    if _hostname(request.headers.get("host", "")) not in LOCAL_HOSTS:
        return "only on the PC itself: open http://localhost:8766"
    origin = request.headers.get("origin")
    if origin and _hostname(origin) not in LOCAL_HOSTS:
        return "only from the dashboard on this PC"
    return None


def _authorized(header: str, password: str) -> bool:
    if not header.lower().startswith("basic "):
        return False
    try:
        supplied = base64.b64decode(header[6:]).decode("utf-8", "replace").partition(":")[2]
    except Exception:
        return False
    return hmac.compare_digest(supplied.encode(), password.encode())


def install(app) -> dict:
    password = os.environ.get("LE_DASH_PASSWORD", "")
    cloud = os.environ.get("LE_CLOUD") == "1"
    if cloud and len(password) < 12:
        raise SystemExit("LE_CLOUD=1 needs LE_DASH_PASSWORD (12+ characters): refusing to put the dashboard on the internet unprotected")

    if password:
        @app.middleware("http")
        async def password_gate(request, call_next):
            if request.url.path.startswith(OPEN_PATHS) or _authorized(request.headers.get("authorization", ""), password):
                return await call_next(request)
            await asyncio.sleep(1.0)     # slows password guessing
            return Response("Login required", status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="Liquidity Engine", charset="UTF-8"'})

    if cloud:
        @app.middleware("http")
        async def paper_only(request, call_next):
            if request.method == "POST" and request.url.path in CLOUD_BLOCKED:
                return JSONResponse({"ok": False, "error": "cloud mode is paper only - live trading runs TradingView -> bridge"}, 403)
            return await call_next(request)

        from .live import BOT
        start = BOT.start

        def paper_start(cfg=None, *a, **kw):
            cfg = dict(cfg or {})
            if cfg.get("adapter", "paper") != "paper" or cfg.get("armed"):
                return {"ok": False, "error": "cloud mode is paper only - live trading runs TradingView -> bridge"}
            return start(cfg, *a, **kw)
        BOT.start = paper_start          # also covers the autostart resume path

        if os.environ.get("LE_PAPER_AUTOSTART", "1") == "1":
            # a fresh cloud container has no autostart.json: start the paper bot once the server is up
            import threading
            import time

            def kick():
                time.sleep(30)
                if not BOT.running:
                    print("[cloud] starting paper bot:", paper_start({"sym": "NQ", "tf": "5m", "adapter": "paper",
                                                                       "data_source": "yahoo", "poll_sec": 60}), flush=True)
            threading.Thread(target=kick, name="cloud-paper-autostart", daemon=True).start()

    return {"password": bool(password), "cloud": cloud}
