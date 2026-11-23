"""NQ Liquidity Bot - API + dashboard server.   python server.py  ->  http://127.0.0.1:8765"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from engine import analytics, backtest, robust
from engine.data import available, load
from engine.instruments import INSTRUMENTS
from engine.live import BOT
from engine.model import DEFAULTS
# ---- LITE MODE ---- (engine/lite.py: data/lite.json {"on": true} or LE_LITE=1; read-only add-ons off, 100 days of history;
# trading decisions unchanged, tests/test_lite.py). Before anything below reads the LE_* switches it sets.
from engine import lite as _lite
LITE = _lite.settings()
if LITE["on"]:
    _lite.apply_env()
    _lite.install(BOT, LITE)
    print(f"[lite] LITE mode on ({LITE.get('why')}): add-ons off, {BOT.lite['hist_days']} days of history", flush=True)
# ---- END LITE MODE ----

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
app = FastAPI(title="NQ Liquidity Bot")
# ---- CLOUD GUARD ----
from engine import cloud_guard as _cg   # password gate (LE_DASH_PASSWORD) + paper-only cloud mode (LE_CLOUD=1)
_cg.install(app)
# ---- END CLOUD GUARD ----
# ---- CROSS-SITE GUARD ---- (engine/cross_site.py, day-security 2026-11-20): a POST from another web site / a rebinding name is refused
from engine import cross_site as _xs
_xs.install(app)
# ---- END CROSS-SITE GUARD ----


@app.middleware("http")
async def no_stale_assets(request, call_next):
    # the dashboard changes often: make browsers revalidate JS/CSS/HTML instead of running a cached old copy
    resp = await call_next(request)
    if not request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp
_cache: OrderedDict = OrderedDict()
_lock = threading.Lock()
_refresh = {"running": False, "log": "", "finished": None}


def _np(o):
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "tolist"):
        return o.tolist()
    return str(o)


def J(obj, status=200):
    return Response(json.dumps(obj, default=_np, separators=(",", ":")), media_type="application/json", status_code=status)


def _key(*parts):
    return hashlib.md5(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def cached(key, fn):
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    val = fn()
    with _lock:
        _cache[key] = val
        while len(_cache) > 40:
            _cache.popitem(last=False)
    return val


def _bt(body):
    sym, tf = body.get("sym", "NQ"), body.get("tf", "5m")
    params, plan = body.get("params", {}), body.get("plan", "builder_50k")
    mt = os.path.getmtime(os.path.join(ROOT, "data", f"{sym}_{tf}.csv"))
    return cached(_key("bt", sym, tf, params, plan, mt), lambda: backtest.run(sym, tf, params, plan))


@app.get("/api/meta")
def meta():
    return J({"available": available(), "defaults": DEFAULTS, "plans": analytics.PLANS, "instruments": INSTRUMENTS,
              "server_time": int(time.time())})


@app.get("/api/bars")
def bars(sym: str = "NQ", tf: str = "5m", start: int | None = None, end: int | None = None):
    b = load(sym, tf)
    a, z = 0, len(b)
    if start:
        a = int((b.t < start).sum())
    if end:
        z = int((b.t <= end).sum())
    return J({"sym": sym, "tf": tf, "t": b.t[a:z].tolist(), "o": b.o[a:z].tolist(), "h": b.h[a:z].tolist(),
              "l": b.l[a:z].tolist(), "c": b.c[a:z].tolist(), "v": b.v[a:z].tolist(),
              "d": b.date_str[a:z], "mod": b.mod[a:z].tolist()})


@app.post("/api/backtest")
async def api_backtest(req: Request):
    body = await req.json()
    try:
        return J(_bt(body))
    except Exception as e:
        return J({"error": str(e)}, 400)


@app.post("/api/montecarlo")
async def api_mc(req: Request):
    body = await req.json()
    r = _bt(body)
    plan = analytics.PLANS[body.get("plan", "builder_50k")]
    pnls = [d["pnl"] for d in r["days"]]
    return J(analytics.monte_carlo(pnls, plan, runs=int(body.get("runs", 2000)), horizon=int(body.get("horizon", 60))))


@app.post("/api/stress")
async def api_stress(req: Request):
    body = await req.json()
    sym, tf, params = body.get("sym", "NQ"), body.get("tf", "5m"), body.get("params", {})
    return J(cached(_key("stress", sym, tf, params), lambda: robust.stress(sym, tf, params)))


@app.post("/api/exitstudy")
async def api_exitstudy(req: Request):
    body = await req.json()
    sym, tf, params = body.get("sym", "NQ"), body.get("tf", "5m"), body.get("params", {})
    split = body.get("split", "2026-09-22")
    mt = os.path.getmtime(os.path.join(ROOT, "data", f"{sym}_{tf}.csv"))
    return J(cached(_key("exit", sym, tf, params, split, mt), lambda: robust.exit_study(sym, tf, params, split)))


@app.post("/api/placebo")
async def api_placebo(req: Request):
    body = await req.json()
    sym, tf, params = body.get("sym", "NQ"), body.get("tf", "5m"), body.get("params", {})
    mt = os.path.getmtime(os.path.join(ROOT, "data", f"{sym}_{tf}.csv"))
    return J(cached(_key("placebo", sym, tf, params, mt), lambda: robust.placebo(sym, tf, params)))


@app.post("/api/news")
async def api_news(req: Request):
    from engine import news
    from engine.model import merge_params
    body = await req.json()
    p = merge_params(body.get("params", {}))
    now = int(time.time())
    vol = news.volatility()
    ff = news.ff_calendar()
    up = news.upcoming_events(now)
    out = {
        "now": now,
        "guard": news.guard(now, p, vol, up),
        "upcoming": up[:40],
        "calendar": ff,
        "headlines": news.headlines(),
        "volatility": vol,
        "earnings": news.earnings(),
        "nq_range": news.nq_range_state(load("NQ", "5m")),
        "rules": {k: p[k] for k in ("news_filter", "news_before_min", "news_after_min", "fomc_pm_off", "news_flatten_min",
                                     "news_day_skip", "vix_max", "vix_min", "day_range_max")},
    }
    return J(out)


@app.post("/api/firms")
async def api_firms(req: Request):
    """Same strategy run through every firm's evaluation rules."""
    body = await req.json()
    r = _bt({**body, "plan": "builder_50k"})
    pnls = [d["pnl"] for d in r["days"]]
    lows = [d.get("low_intraday", min(0.0, d["pnl"])) for d in r["days"]]
    rows = []
    for key, pl in analytics.PLANS.items():
        if key == "builder_50k_addon":
            continue
        roll = analytics.rolling_evals(r["days"], pl)
        mc = cached(_key("firm-mc", key, body.get("params", {}), body.get("sym")),
                    lambda pl=pl: analytics.monte_carlo(pnls, pl, runs=1500, horizon=60))
        rows.append({"key": key, "name": pl["name"], "target": pl["target"], "mll": pl["mll"], "lock": pl.get("lock_above"),
                     "dll": pl.get("dll"), "eval_consistency": pl.get("eval_consistency"), "min_days": pl.get("min_days_eval"),
                     "max_minis": pl.get("max_minis"), "split": pl.get("split"), "automation": pl.get("automation"),
                     "price": pl.get("price"), "flat": pl.get("flat"),
                     "rolling_pass": roll["pass_rate"], "rolling_n": roll["completed"], "avg_days": roll["avg_days_to_pass"],
                     "mc_pass": mc["pass_prob"], "mc_fail": mc["fail_prob"], "mc_days": mc["median_days_to_pass"],
                     "funded_paid": mc["funded"]["avg_paid_to_trader"], "bot_ok": not str(pl.get("automation", "")).startswith("PROHIBITED")})
    return J({"rows": rows, "note": "Rules from each firm's help center as of Oct 2026. Re-check before buying."})


_disc = {"proc": None}


@app.get("/api/discovery")
async def api_discovery():
    """Confluence discovery leaderboard (cached scan of every recorded feature across every period)."""
    path = os.path.join(ROOT, "data", "discovery.json")
    running = _disc["proc"] is not None and _disc["proc"].poll() is None
    data = None
    if os.path.exists(path):
        with open(path) as fh:
            data = json.load(fh)
    return J({"running": running, "data": data})


@app.post("/api/discovery/run")
async def api_discovery_run():
    if _disc["proc"] is None or _disc["proc"].poll() is not None:
        _disc["proc"] = subprocess.Popen([sys.executable, "-m", "engine.discovery"], cwd=ROOT,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return J({"running": True})


@app.post("/api/regime")
async def api_regime(req: Request):
    """Strategy result by market regime, real CME futures only (NQ by month + ES). No CFD data is used anywhere."""
    body = await req.json()
    params = body.get("params", {})
    mts = {s: os.path.getmtime(os.path.join(ROOT, "data", f"{s}_5m.csv"))
           for s in ("NQ", "ES") if os.path.exists(os.path.join(ROOT, "data", f"{s}_5m.csv"))}

    def work():
        import calendar
        runs, segs = {}, []
        for sym in mts:
            runs[sym] = backtest.run(sym, "5m", {**params, "dd_aware": False, "daily_max_loss": 1e9}, light=True)
        if "NQ" in runs:                 # one row per calendar month of NQ futures history we hold
            for ym in sorted({d["date"][:7] for d in runs["NQ"]["days"]}):
                y, m = int(ym[:4]), int(ym[5:])
                segs.append((f"NQ futures · {calendar.month_abbr[m]} {y}", "NQ", f"{ym}-01", f"{ym}-31"))
            segs.append(("NQ futures · all", "NQ", None, None))
        if "ES" in runs:
            segs.append(("ES futures · all", "ES", None, None))
        out = []
        for label, sym, a, z in segs:
            rr = runs[sym]
            days = [d for d in rr["days"] if (not a or d["date"] >= a) and (not z or d["date"] <= z)]
            if len(days) < 5:
                continue
            tr = [t for t in rr["trades"] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
            reg = {d["date"]: d.get("regime") for d in days}
            ers = [d["er10"] for d in days if d.get("er10") is not None]
            row = {"period": label, "sym": sym, "from": days[0]["date"], "to": days[-1]["date"], "days": len(days),
                   "er10": round(float(sum(ers) / len(ers)), 3) if ers else None,
                   "total": {"trades": len(tr), "avg_r": round(sum(t["pnl_r"] for t in tr) / len(tr), 3) if tr else None,
                             "pnl": round(sum(t["pnl"] for t in tr), 2)}}
            for g in ("rotational", "trending"):
                tg = [t for t in tr if reg.get(t["day"]) == g]
                row[g] = {"trades": len(tg), "days": sum(1 for d in days if d.get("regime") == g),
                          "avg_r": round(sum(t["pnl_r"] for t in tg) / len(tg), 3) if tg else None,
                          "pnl": round(sum(t["pnl"] for t in tg), 2)}
            out.append(row)
        return out
    return J({"periods": cached(_key("regime-fut", params, mts), work), "source": "CME futures only"})


@app.get("/api/markets")
def api_markets():
    from engine import markets
    return J(markets.snapshot())


@app.get("/api/alerts")
def api_alerts_get():
    from engine import alerts
    return J(alerts.public())


@app.post("/api/alerts")
async def api_alerts_save(req: Request):
    from engine import alerts
    return J(alerts.save(await req.json()))


@app.post("/api/alerts/send")
async def api_alerts_send(req: Request):
    from engine import alerts
    body = await req.json()
    return J(alerts.send(body.get("text", "Liquidity Engine test alert ✅"), body.get("kind", "signal"), force=bool(body.get("force"))))


# phone app notifications (Web Push, engine/push.py): data/push.json holds the VAPID private key + the app's subscription
# codes (gitignored); the API never returns the private key or an endpoint
@app.get("/api/push")
def api_push_get():
    # 2026-11-19: the PC's own key + the phones that turned on notifications in Olympus (engine/push.pc_config; no cloud link)
    from engine import push
    cfg = push.pc_config()
    return J({**push.status(cfg), "linked": bool(cfg.get("private") and cfg.get("subs")), "sync_error": None,
              "heartbeat_key": bool(push.pc_public_key()), "recent": push.pc_notifier().log[-10:]})


@app.post("/api/push")
async def api_push_save(req: Request):
    from engine import push
    try:
        return J({"ok": True, **push.save_pc_config(await req.json())})
    except ValueError as e:
        return J({"ok": False, "error": str(e)}, 400)


@app.post("/api/push/test")
def api_push_test():
    # 2026-11-20 (owner: "notifications for trade entries I never got one from today. And results"): a TEST entry + TEST close, the
    # real trade alerts' words, on EVERY route (the Olympus phones + the private ntfy topic), with what each answered
    # (engine/alert_check; never recorded as a trade). One test a minute (no login here: a repeated tap or a script on the home
    # network must not spend ntfy's day); the ntfy half waits when the day's room is down to the trade alerts' reserve.
    from engine import alert_check
    r = alert_check.send_test()
    a, rt = r.get("app") or {}, r.get("routes") or {}
    if r.get("cooldown"):
        return J({"ok": False, "error": r.get("say") or "one test a minute", "cooldown": r["cooldown"]}, 429)
    if not rt.get("phones") and not rt.get("ntfy") and not rt.get("bus"):    # Telegram / Discord (engine/alert_bus) count too
        return J({"ok": False, "error": "no alert route on this PC: open Olympus from the iPhone's Home Screen and tap Allow notifications, "
                                        "and/or run python tools/pc_report.py --setup", "warn": rt.get("warn")}, 400)
    return J({"ok": bool(a.get("sent")) or r.get("ntfy") == "sent", **{k: a.get(k) for k in ("sent", "devices", "gone", "errors")},
              "ntfy": r.get("ntfy"), "say": r.get("say"), "warn": rt.get("warn")})


@app.get("/api/gamma")
def api_gamma():
    from engine import gamma
    try:
        nq = load("NQ", "5m")
        live = gamma.live_levels(float(nq.c[-1]))
    except Exception as e:
        live = {"error": str(e)}
    h = gamma.history()
    last = h.iloc[-1] if len(h) else None
    hist = None if last is None else {"date": str(last["date"]), "gex_bn": round(float(last["gex_bn"]), 2),
                                      "gex_pct": round(float(last["gex_pct"]), 1), "dix": round(float(last["dix"]), 4),
                                      "series": [{"date": str(r.date), "gex_bn": round(float(r.gex_bn), 2)} for r in h.tail(120).itertuples()]}
    return J({"live": live, "spx": hist})


@app.post("/api/optimize")
async def api_opt(req: Request):
    body = await req.json()
    sym, tf, params = body.get("sym", "NQ"), body.get("tf", "5m"), body.get("params", {})
    x, y = body["x"], body["y"]
    return J(cached(_key("opt", sym, tf, params, x, y),
                    lambda: robust.neighbourhood(sym, tf, params, (x["name"], x["values"]), (y["name"], y["values"]))))


@app.post("/api/data/refresh")
def api_refresh():
    if _refresh["running"]:
        return J({"ok": False, "error": "refresh already running"})
    from engine import pcbars
    if pcbars.no_yahoo():               # data/fetch.py appends Yahoo bars to data/*.csv: off with no_yahoo (owner 2026-10-19)
        return J({"ok": False, "error": "no Yahoo (live_model.json no_yahoo): refresh the history with the TradingView export "
                                        "(tools/grab_tv_export.py); NinjaTrader's bars come in by themselves"})

    def work():
        _refresh.update(running=True, log="")
        p = subprocess.run([sys.executable, os.path.join(ROOT, "data", "fetch.py")], capture_output=True, text=True)
        _refresh.update(running=False, log=p.stdout + p.stderr, finished=int(time.time()))
        _cache.clear()

    threading.Thread(target=work, daemon=True).start()
    return J({"ok": True})


@app.get("/api/data/refresh")
def api_refresh_status():
    return J(_refresh)


@app.post("/api/live/start")
async def live_start(req: Request):
    body = await req.json()
    res = BOT.start(body)
    if res.get("ok"):
        _autostart_save(body)            # AUTOSTART block: remember it so a crash / reboot can resume (secrets stripped)
    return J(res)


def _handsoff(kind, detail):
    """The weekly hands-off score (engine/handsoff.py): a person pressed stop / kill. Never raises."""
    try:
        from engine import handsoff as _ho
        _ho.record(kind, "dashboard", detail, path=_ho.path_for(BOT))
    except Exception:
        pass


@app.post("/api/live/stop")
def live_stop():
    _autostart_clear("stop")             # AUTOSTART block: an intentional stop stays stopped
    if BOT.running:
        _handsoff("stop", "Stop on the PC dashboard")
    return J(BOT.stop())


@app.post("/api/live/kill")
def live_kill():
    try:                                 # the kill switch (HOLD TO KILL) also turns the real-account auto-resume off
        from engine import autoresume as _ar
        if _ar.disable("kill switch"):
            _autostart_log("auto-resume turned OFF by the kill switch")
    except Exception as e:
        print(f"[autostart] could not turn auto-resume off: {e}", flush=True)
    _handsoff("kill", "HOLD TO KILL on the PC dashboard")
    return J(BOT.kill_switch())


@app.post("/api/live/poll")
def live_poll():
    if not BOT.cfg:
        BOT.cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "params": {}}
        from engine.live import PaperAdapter
        BOT.adapter = PaperAdapter({})
        BOT.started_at = int(time.time())
    try:
        BOT.poll_once()
        return J(BOT.snapshot())
    except Exception as e:
        return J({"error": str(e)}, 500)


@app.get("/api/live/state")
def live_state():
    return J(BOT.snapshot())


@app.get("/api/next/blitz")
def blitz_view():
    """BLITZ, the scalper (read-only; the PC dashboard's BLITZ page, web_next/js/next/blitz.js): engine/blitz.card of the
    bot's PAPER shadow (state, band, signals, both paper ledgers, evals) + account C's block when it is on (no secrets)."""
    try:
        from engine import blitz as BZ
        out = {"card": BZ.card(getattr(BOT, "blitz", None)), "t": int(time.time())}
        ac = getattr(BOT, "acct_c", None)
        if ac is not None:
            try:
                out["account_c"] = ac.hb_block()
            except Exception as e:
                out["account_c"] = {"error": f"{e.__class__.__name__}: {e}"[:200]}
        try:                                                 # the Start page's BLITZ slot (data/account_c.json), never the phrase
            from engine import go as GO
            sl = GO.blitz_status()
            out["slot"] = {k: sl.get(k) for k in ("on", "name", "sim", "armed", "start", "stage", "problem", "say")}
        except Exception as e:
            out["slot"] = {"error": f"{e.__class__.__name__}: {e}"[:200]}
        return J(out)
    except Exception as e:                                   # never 500 the dashboard over a page
        return J({"error": f"{e.__class__.__name__}: {e}"[:200]}, 500)


# ------------------------------------------------------------------ phone access: this computer's private addresses
@app.get("/api/net")
def api_net(request: Request):
    import ipaddress
    import socket
    lan, ts = [], None
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            a = ipaddress.ip_address(ip)
            if a in ipaddress.ip_network("100.64.0.0/10"):      # Tailscale / CGNAT range
                ts = ip
            elif a.is_private and ip not in lan:
                lan.append(ip)
    except Exception:
        pass
    return J({"lan": lan, "tailscale": ts, "port": request.url.port or 80, "host": socket.gethostname()})


# ------------------------------------------------------------------ TradingView: Pine strategy, data import, webhook
TV_CFG = os.path.join(ROOT, "data", "tv.json")
_tv_hook = {"recent": []}


def _tv_cfg():
    import secrets
    cfg = {}
    if os.path.exists(TV_CFG):
        with open(TV_CFG) as fh:
            cfg = json.load(fh)
    if not cfg.get("key"):
        cfg["key"] = secrets.token_urlsafe(18)
        with open(TV_CFG, "w") as fh:
            json.dump(cfg, fh)
    return cfg


def _tv_data_status():
    out = {}
    for sym in ("NQ", "ES"):
        path = os.path.join(ROOT, "data", f"{sym}_5m.csv")
        if not os.path.exists(path):
            continue
        try:
            b = load(sym, "5m")
            days = sorted(set(b.date_str))
            imp_path = os.path.join(ROOT, "data", f"{sym}_imported_days.json")
            imported = json.load(open(imp_path)) if os.path.exists(imp_path) else []
            out[sym] = {"from": days[0], "to": days[-1], "days": len(days), "bars": int(len(b.t)), "imported_days": len(imported)}
        except Exception as e:
            out[sym] = {"error": str(e)}
    return out


@app.get("/api/tv/status")
def api_tv_status():
    cfg = _tv_cfg()
    return J({"data": _tv_data_status(), "hook": {"key": cfg["key"], "public_base": cfg.get("public_base", ""), "recent": _tv_hook["recent"][:20]}})


@app.get("/api/tv/pine")
def api_tv_pine(download: int = 0):
    path = os.path.join(ROOT, "tradingview", "liquidity_engine.pine")
    if download:
        return FileResponse(path, filename="liquidity_engine.pine", media_type="text/plain")
    with open(path, encoding="utf-8") as fh:
        # CORS open on purpose: the script is public text and the TradingView page fetches it to fill the Pine Editor
        return Response(fh.read(), media_type="text/plain; charset=utf-8", headers={"Access-Control-Allow-Origin": "*"})


@app.post("/api/tv/hook")
async def api_tv_hook(req: Request):
    import secrets
    body = await req.json()
    cfg = _tv_cfg()
    if body.get("rotate"):
        cfg["key"] = secrets.token_urlsafe(18)
    if "public_base" in body:
        cfg["public_base"] = str(body["public_base"]).strip().rstrip("/")
    with open(TV_CFG, "w") as fh:
        json.dump(cfg, fh)
    return J({"key": cfg["key"], "public_base": cfg.get("public_base", ""), "recent": _tv_hook["recent"][:20]})


@app.post("/api/tv/webhook")
async def api_tv_webhook(req: Request, key: str = ""):
    """TradingView alert webhook. The key in the URL is the only credential; payload is data, shown in the live feed."""
    cfg = _tv_cfg()
    if not key or not cfg.get("key") or not hmac.compare_digest(str(key), str(cfg["key"])):     # constant-time compare
        return J({"error": "bad key"}, 403)
    raw = (await req.body())[:4000].decode("utf-8", "replace")
    try:
        body = json.loads(raw)
    except Exception:
        body = {"text": raw}
    evt = {"t": int(time.time()), "body": body}
    _tv_hook["recent"].insert(0, evt)
    del _tv_hook["recent"][50:]
    text = body.get("text") if isinstance(body, dict) and "text" in body else \
        f"{body.get('event', 'alert')} {body.get('symbol', '')} @ {body.get('price', '')} {body.get('note', '')}".strip() if isinstance(body, dict) else raw
    BOT._log("tradingview", f"TradingView: {text}"[:300])
    try:
        from engine import alerts
        alerts.send(f"📡 TradingView · {text}"[:400], "signal")
    except Exception:
        pass
    return J({"ok": True})


@app.post("/api/tv/import")
async def api_tv_import(req: Request, sym: str = "NQ"):
    """Import a TradingView 'Export chart data' CSV (ISO or unix time) into the bot's futures history."""
    import importlib.util
    sym = sym.upper()
    if sym not in ("NQ", "ES"):
        return J({"error": "sym must be NQ or ES"}, 400)
    text = (await req.body()).decode("utf-8-sig", "replace")
    spec = importlib.util.spec_from_file_location("import_futures", os.path.join(ROOT, "data", "import_futures.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        info = mod.tradingview_text(sym, text)
    except Exception as e:
        return J({"error": f"could not parse this file: {e}"}, 400)
    _cache.clear()
    return J(info)


# ---- LIVE TRADING (tradovate) ----
from engine import golive as _golive
from engine import tradovate as _tv
from engine import ninjatrader as _nt

_live_arm = {"armed": False, "at": None, "adapter": "paper"}     # memory only, never written to disk


@app.get("/api/live/adapters")
def live_adapters():
    st = _tv.env_status()
    return J({"adapters": [
        {"name": "paper", "label": "Paper (simulated)", "configured": True},
        {"name": "tradovate-demo", "label": "Tradovate DEMO", "configured": st["present"]},
        {"name": "tradovate-live", "label": "Tradovate LIVE (MFFU)", "configured": st["present"] and st["env"] == "live"},
        {"name": "ninjatrader", "label": "NinjaTrader 8 (Sim101 first; ninjatrader/SETUP.md)", "configured": _nt.folder_ready()},
    ], "env": st["env"], "missing": st["missing"], "account": st["account"], "phrase": _tv.LIVE_PHRASE,
        "armed": _live_arm["armed"], "armed_at": _live_arm["at"], "bot_running": BOT.running, "bot_adapter": BOT.cfg.get("adapter")})


@app.post("/api/live/arm")
async def live_arm(req: Request):
    body = await req.json()
    if body.get("disarm"):
        _live_arm.update({"armed": False, "at": None, "adapter": "paper"})
        _tv.ARM.update(_live_arm)
        BOT._log("risk", "DISARMED")
        return J({"ok": True, "armed": False})
    if (body.get("phrase") or "").strip() != _tv.LIVE_PHRASE:
        return J({"ok": False, "error": f"phrase does not match; type exactly: {_tv.LIVE_PHRASE}"}, 400)
    if _tv.env_status()["env"] != "live":
        return J({"ok": False, "error": "TRADOVATE_ENV is not 'live' - arming is pointless; restart the server with the live env first"}, 400)
    if not _tv.env_status()["present"]:
        return J({"ok": False, "error": "credentials missing in environment"}, 400)
    _live_arm.update({"armed": True, "at": int(time.time()), "adapter": "tradovate-live"})
    _tv.ARM.update(_live_arm)
    BOT._log("risk", "LIVE ARMED by operator (phrase accepted)")
    return J({"ok": True, "armed": True, "at": _live_arm["at"]})


@app.post("/api/live/golive")
async def live_golive(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    cfg = {k: v for k, v in body.items() if k != "roundtrip"}
    try:
        return J(_golive.run(cfg, roundtrip=bool(body.get("roundtrip"))))
    except Exception as e:
        return J({"ok": False, "error": str(e), "steps": []}, 500)
# ---- END LIVE TRADING ----


# ---- MEMORY ----
# Persistent trade memory (engine/memory.py, data/memory.db): every completed routed paper / live trade, its exit-signal
# counterfactuals and the operator's notes. Read-only reporting: nothing here changes sizing or trading parameters.
from engine.memory import MEMORY as _MEM


def _mem_src(source: str):
    s = (source or "").strip().lower()
    if s in ("", "realised", "realized"):
        return None                      # paper + live
    if s == "all" or s in ("paper", "live", "backtest"):
        return s
    raise ValueError("source must be paper, live, backtest, realised or all")


@app.get("/api/memory/stats")
def memory_stats(learn_min: int | None = None, threshold: float | None = None, sym: str = ""):
    lm = int(learn_min if learn_min is not None else DEFAULTS["exit_learn_min"])
    th = float(threshold if threshold is not None else DEFAULTS["exit_learn_threshold"])
    try:
        out = {"realised": _MEM.stats(None, lm, th), "paper": _MEM.stats("paper", lm, th), "live": _MEM.stats("live", lm, th),
               "counts": {s: _MEM.count((s,)) for s in ("paper", "live", "backtest")},
               "learner": {"learn_min": lm, "threshold": th, "signals": _MEM.signal_summary(("paper", "live"), lm, th),
                           "seed_default": bool(DEFAULTS.get("memory_seed")),
                           "seedable": {s: len(v) for s, v in _MEM.exit_gains(("paper", "live"), sym=sym or None).items()}},
               "calibration": _MEM.calibration(), "state": _MEM.states(), "db": os.path.relpath(_MEM.path, ROOT)}
        return J(out)
    except Exception as e:
        return J({"error": f"memory unavailable: {e}"}, 500)


@app.get("/api/memory/trades")
def memory_trades(source: str = "", limit: int = 200):
    try:
        return J({"trades": _MEM.recent(max(1, min(int(limit), 2000)), _mem_src(source))})
    except ValueError as e:
        return J({"error": str(e)}, 400)


@app.post("/api/memory/note")
async def memory_note(req: Request):
    body = await req.json()
    try:
        tid = int(body.get("trade_id"))
    except (TypeError, ValueError):
        return J({"error": "trade_id required"}, 400)
    r = _MEM.add_note(tid, str(body.get("text") or ""))
    return J(r, 200 if r.get("ok") else 404)


@app.get("/api/memory/export")
def memory_export():
    name = f"liquidity_memory_{time.strftime('%Y-%m-%d')}.csv"
    return Response(_MEM.export_csv(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
# ---- END MEMORY ----


# ---- AUTOSTART ----
# Unattended running (engine/watchdog.py, engine/keepawake.py, scripts/run_bot.ps1). data/autostart.json remembers
# the last successful /api/live/start; on server start a paper / Tradovate-DEMO bot resumes by itself. Live never
# auto-resumes. /api/live/stop and /api/live/kill delete the record. A heartbeat thread alerts on stalled polls / a
# stale feed and keeps the PC awake while the bot runs.
from engine import autoresume as _ar
from engine import autoupdate as _au
from engine import heartbeat as _hb
from engine import keepawake as _ka
from engine import watchdog as _wd

_AUTOSTART = {"path": _wd.AUTOSTART_PATH}


def _autostart_log(text):
    print(f"[autostart] {time.strftime('%Y-%m-%d %H:%M:%S')} {text}", flush=True)
    try:
        BOT._log("system", f"Autostart: {text}")
    except Exception:
        pass


def _autostart_alert(text):
    try:
        from engine import alerts
        alerts.send(text, "system", force=True)
    except Exception as e:
        print(f"[autostart] alert failed: {e}", flush=True)


def _autostart_save(cfg):
    try:
        rec = _wd.save(cfg, _tv.env_status()["env"], _AUTOSTART["path"], phrases=(_tv.LIVE_PHRASE,))
        _autostart_log(f"saved start config (adapter={rec['cfg'].get('adapter', 'paper')}, mode={rec['mode']})")
    except Exception as e:
        _autostart_log(f"could not save autostart.json: {e}")


def _autostart_clear(why):
    try:
        if _wd.clear(_AUTOSTART["path"]):
            _autostart_log(f"autostart.json cleared ({why})")
    except Exception as e:
        _autostart_log(f"could not clear autostart.json: {e}")


class _KillClearsAutostart:
    """Pure ASGI middleware: a successful POST /api/live/kill also deletes autostart.json (route body untouched)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") != "/api/live/kill":
            return await self.inner(scope, receive, send)
        status = {}

        async def _send(msg):
            if msg.get("type") == "http.response.start":
                status["code"] = msg.get("status")
            await send(msg)
        await self.inner(scope, receive, _send)
        if status.get("code") == 200:
            _autostart_clear("kill switch")


app.add_middleware(_KillClearsAutostart)
# hidden bots (owner 2026-11-15, dashboard_view.json "hidden_bots", default ["blitz"]): GET /api/* JSON answers go out
# without them (engine/hidden_bots.py); the bot itself keeps running on paper; /api/next/blitz* answer as before
from engine.hidden_bots import ScrubMiddleware as _HideBots
app.add_middleware(_HideBots)
WATCHDOG = _wd.Watchdog(BOT, send=_autostart_alert, keepawake=_ka.KEEPAWAKE)
AUTOUPDATE = _au.DailyUpdater(BOT)       # owner opt-in: python -m engine.autoupdate --enable
HEARTBEAT = _hb.Heartbeat(BOT, log=lambda t: print(t, flush=True))   # pushes "I'm alive" to the heartbeat branch (LE_HEARTBEAT=1)
from engine import live_publish as _lp
# the phone app's live.json (engine/live_publish.py): the Home essentials pushed to branch `live` of the public Pages repo
# every 60 s while the bot runs (5 min otherwise), read by tools/web_public/live.js; on with the heartbeat (LE_HEARTBEAT=1)
LIVEPUB = _lp.Publisher(BOT, HEARTBEAT, log=lambda t: print(t, flush=True))
from engine import fill_audit as _fa
# execution quality (engine/fill_audit.py): copies the ledger / NinjaTrader fills each minute, compares them with the LIT backtest
# on the same bars after each exit and each session, pushes slipped fills / missed trades; read-only (LE_EXEC_AUDIT=0 = off)
EXEC_AUDIT = _fa.Watcher(BOT, log=lambda t: print(t, flush=True))
from engine import pc_health as _pch
# PC health watchdog + weekly schedules (engine/pc_health.py, read-only, its own thread, never in the poll): CPU / RAM / disk /
# NinjaTrader / bot memory / OneDrive / clock / poll lines in the heartbeat ("pc_health"), the Sunday 15:30 ET PC self-test
# and the 17:30 ET readiness push (engine/pc_selftest.py, engine/readiness.py); LE_PC_WATCH=0 = off
PCWATCH = _pch.Watcher(BOT)
_pch.WATCHER = PCWATCH
from engine import report_keeper as _rk
# the phone report keeper (engine/report_keeper.py): re-installs the 15-minute task OlympusPCReport when it is missing and runs
# tools/pc_report.py itself when the task is late (ntfy status + trade pushes); read-only towards the bot (LE_REPORT_KEEPER=0 = off)
REPORT_KEEPER = _rk.Keeper()
from engine import state_pulse as _sp
# the state pulse (engine/state_pulse.py, night-truth 2026-11-22): a bot state CHANGE (running <-> stopped, armed / disarmed, an entry
# block, a trade opened / closed) posts the phone's status at once (debounced 30 s, <= 24 a day), not at the next 15-minute report
PULSE = _sp.Pulse(BOT, HEARTBEAT, LIVEPUB)


def _open_nt():
    """After a reboot: open NinjaTrader when it is not running (engine/go.ensure_ninjatrader, no wait)."""
    from engine import go as _go
    _go.ensure_ninjatrader(wait_s=0, connected=lambda: None, sleep=lambda s: None)


def _autostart_resume():
    rec = _wd.load(_AUTOSTART["path"])
    marker = _au.take_restart_marker()   # set when this restart follows an auto-update (engine/autoupdate.py)
    if marker:                           # night-verify: check the new pieces on this PC, one phone message (read-only, own thread,
        try:                             # 90 s later so the bot resumes first; never blocks this restart)
            from engine import post_update_check as _puc
            _puc.start_bg(str(marker.get("sha") or "") or None)
        except Exception:
            pass
    try:                                 # hands-off score: a restart nobody asked for (engine/handsoff.py)
        from engine import handsoff as _ho
        _ho.note_server_start(marker, path=_ho.path_for(BOT))
    except Exception:
        pass
    d = _wd.decide_resume(rec, time.time(), _tv.env_status()["env"])
    info = {"checked_at": int(time.time()), "record": bool(rec), "mode": d["mode"], "reason": d["reason"],
            "resumed": False, "result": None, "after_update": (marker or {}).get("sha")}
    if rec and isinstance(rec.get("cfg"), dict):
        info.update(adapter=rec["cfg"].get("adapter", "paper"), saved_at=rec.get("saved_at"))
    WATCHDOG.autostart_info = info
    if not d["resume"] and d["mode"] == "live" and rec and isinstance(rec.get("cfg"), dict):
        # a real account: only with the owner's opt-in (engine/autoresume.py, every live lock still applies)
        optin = _ar.load()
        if optin and optin.get("enabled"):
            r = _ar.resume_live(BOT, rec["cfg"], marker, notify=_au.notify, log=_autostart_log,
                                still_on=lambda: bool(_wd.load(_AUTOSTART["path"])),    # the dashboard switch still on Run
                                open_nt=_open_nt)
            info.update(resumed=bool((r.get("result") or {}).get("ok")), reason=r.get("reason"), result=r.get("result"),
                        auto_resume=True)
            return
        if marker:
            acct = rec["cfg"].get("nt_account") or "your eval"
            _au.notify(f"Updated to {str(marker.get('sha'))[:7]}",
                       f"Bot is stopped on your eval ({acct}): type the start command to resume "
                       f"(python -m engine.ninjatrader --start --account \"{acct}\" --confirm ...)",
                       key=f"auto:stopped:{str(marker.get('sha'))[:10]}")
    if not d["resume"]:
        _autostart_log(f"no resume: {d['reason']}")
        if rec:
            _autostart_alert(f"Liquidity Engine server restarted; bot NOT resumed: {d['reason']}")
        return
    if BOT.running:
        info["reason"] = "bot already running"
        return
    try:
        res = BOT.start(d["cfg"])
    except Exception as e:
        res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
    info.update(resumed=bool(res.get("ok")), result=res)
    if res.get("ok"):
        _autostart_log(f"RESUMED {d['mode']} bot ({d['cfg'].get('sym', 'NQ')} {d['cfg'].get('tf', '5m')}, "
                       f"adapter={d['cfg'].get('adapter', 'paper')}); restored={res.get('restored')}")
        _autostart_alert(f"Liquidity Engine auto-resumed the {d['mode']} bot after a server restart "
                         f"({d['cfg'].get('sym', 'NQ')} {d['cfg'].get('tf', '5m')}). Restored state: {res.get('restored')}")
    else:
        _autostart_log(f"resume FAILED: {res.get('error')}")
        _autostart_alert(f"Liquidity Engine server restarted but the bot resume FAILED: {res.get('error')}")


def _fix_account_names():
    """The account Names NinjaTrader said do not exist, corrected in the bot's local files (engine/account_rename.py,
    2026-10-27: MFFUEVBLD... -> MFFUEVBLDR...). Never raises."""
    try:
        from engine import account_rename as _ar_n
        r = _ar_n.fix()
        if r.get("changed") or not r.get("ok"):
            print(f"[accounts] {r.get('say')}", flush=True)
            if r.get("changed"):
                _au.notify("Account names fixed", r.get("say", "")[:300] + ". Press Run on the dashboard and type the live "
                           "phrase once (it was given for the old name).", key=f"acct:rename:{int(time.time()) // 3600}")
    except Exception as e:
        print(f"[accounts] name check skipped: {e.__class__.__name__}: {e}", flush=True)


def _migrate_account_b():
    """ATLAS's account block: out of the tracked second_model.json into data/account_b.json (engine/account_b.py), before
    the bot can start, so an older version's write no longer blocks every update. Never raises."""
    try:
        from engine import account_b as _abm
        r = _abm.migrate_local()
        if r.get("status") not in ("clean", "no_git"):
            print(f"[account_b] {r.get('say')}", flush=True)
    except Exception as e:
        print(f"[account_b] migration skipped: {e.__class__.__name__}: {e}", flush=True)


def _ensure_shortcuts():
    """The desktop icons (LE START + LE STOP BOT) and the Startup-folder shortcuts of this version, once (engine/go.py,
    Windows only): an update brings the new icons without a click. Never raises."""
    try:
        from engine import go as _go
        r = _go.ensure_shortcuts()
        if r.get("made") or not r.get("ok"):
            print(f"[shortcuts] {r}", flush=True)
    except Exception as e:
        print(f"[shortcuts] skipped: {e.__class__.__name__}: {e}", flush=True)


def _poll_timing():
    """Per-stage timing of every poll (engine/poll_timing.py, read-only) -> health.poll.stages in the heartbeat and the
    dashboard. LE_POLL_TIMING=0 turns it off. Never raises."""
    try:
        from engine import poll_timing as _pt
        if _pt.enabled():
            _pt.install(BOT)
    except Exception as e:
        print(f"[poll timing] off: {e.__class__.__name__}: {e}", flush=True)


def _autostart_startup():
    WATCHDOG.server_started_at = int(time.time())
    # the crash-loop net FIRST (engine/autoupdate.DailyUpdater.crash_start, redteam 2026-11-21): this start is counted before any
    # bot code runs (a watcher that throws on the new code still counts), and on a rollback nothing resumes on the bad code: the
    # push goes out and the server exits (75), the supervisor starts the old code
    if AUTOUPDATE.crash_start() == "rolled_back":
        return
    _poll_timing()                       # before the bot can start
    if os.environ.get("LE_NO_AUTOSTART") == "1":
        WATCHDOG.autostart_info = {"disabled": "LE_NO_AUTOSTART=1"}
    else:
        _fix_account_names()             # NinjaTrader's real account Names (engine/account_rename.py), before any start
        _migrate_account_b()             # before the resume reads ATLAS's account
        threading.Thread(target=_autostart_resume, name="autostart", daemon=True).start()
        threading.Thread(target=_ensure_shortcuts, name="shortcuts", daemon=True).start()
    WATCHDOG.start()
    HEARTBEAT.start()
    LIVEPUB.start()                      # phone live.json every minute (engine/live_publish.py)
    EXEC_AUDIT.start()
    AUTOUPDATE.start()                   # daily check in the CME halt + hourly outside trading time; nothing until --enable
    try:                                 # day-ready 2026-11-22: 90 s after the server starts, one READY / NOT READY check (engine/readiness; read-only)
        from engine import readiness as _rdy
        _rdy.start_after_boot()
    except Exception as _e:
        print(f"[ready] off: {_e.__class__.__name__}", flush=True)
    PCWATCH.start()                      # PC health + Sunday self-test / readiness (engine/pc_health.py; off in a dev / test server)
    try:
        REPORT_KEEPER.start()            # the phone report even without its Windows task (engine/report_keeper.py; off in a dev / test server)
    except Exception as e:
        print(f"[report keeper] off: {e.__class__.__name__}: {e}", flush=True)
    try:
        PULSE.start()                    # a bot state change reaches the phone at once (engine/state_pulse.py; off in a dev / test server)
    except Exception as e:
        print(f"[pulse] off: {e.__class__.__name__}: {e}", flush=True)


app.router.add_event_handler("startup", _autostart_startup)


# ---- BOT CONTROL ----
# Bot Control center (engine/botctl.py, web_next/js/next/botctl.js): its Start / Stop run exactly what POST /api/live/start
# and /api/live/stop do (BOT.start + the autostart record with the phrase stripped; Stop clears it). The kill switch stays
# POST /api/live/kill. Every live lock (armed + exact phrase + the live env flag, the adapter's _live_gate) is unchanged.
from engine import botctl as _bc


def _botctl_start(body):
    res = BOT.start(body)
    if res.get("ok"):
        _autostart_save(body)
    return res


def _botctl_stop():
    # live_stop() returns a Starlette Response (J(...)); botctl.do_stop needs the dict (dict(Response) raised TypeError, so
    # the Bot Control STOP showed an error although the bot had stopped)
    _autostart_clear("stop")
    if BOT.running:
        _handsoff("stop", "STOP on Bot Control")
    return BOT.stop()


_bc.HOOKS.update(start=_botctl_start, stop=_botctl_stop, heartbeat=HEARTBEAT.status)
# ---- END BOT CONTROL ----


# ---- REMOTE CONTROL ----
# Phone remote control through GitHub (engine/remote_ctl.py, docs/REMOTE_CONTROL.md; LE_REMOTE=1, set by run_bot.ps1): reads
# control/command.json on branch `control` every ~60 s. kill = the HOLD TO KILL path; stop = POST /api/live/stop; flatten =
# BOT.flatten_now; start = Sim / paper only (built inside remote_ctl, never a real account); update / restart only when flat.
from engine import remote_ctl as _rc


def _remote_kill():
    try:
        if _ar.disable("remote kill"):
            _autostart_log("auto-resume turned OFF by the remote kill")
    except Exception as e:
        print(f"[remote] could not turn auto-resume off: {e}", flush=True)
    res = BOT.kill_switch()
    _autostart_clear("remote kill")
    return res


def _remote_stop():
    _autostart_clear("remote stop")
    return BOT.stop()


REMOTE = _rc.RemoteControl(BOT, hooks={"kill": _remote_kill, "stop": _remote_stop, "flatten": BOT.flatten_now,
                                       "start": _botctl_start, "beat": HEARTBEAT.beat},
                           log=lambda t: print(t, flush=True))
app.router.add_event_handler("startup", REMOTE.start)


def _phone_link_startup():
    """engine/phone_link.py: the bot server's own private Tailscale https port (:8444) when 443 belongs to another app.
    Windows only, background thread, never touches 443 or Funnel, never blocks or breaks the bot."""
    try:
        from engine import phone_link as _pl
        _pl.start_background(say=lambda t: print(t, flush=True))
    except Exception as _pl_err:  # noqa: BLE001
        print(f"[phone_link] not started: {_pl_err.__class__.__name__}: {_pl_err}", flush=True)


app.router.add_event_handler("startup", _phone_link_startup)
# "I'm here" check-in, pause until, hands-off score (engine/presence_api.py: /api/next/presence|pause|handsoff; files only)
try:
    from engine import presence_api as _pa
    _pa.bind(BOT)
    app.include_router(_pa.router)
except Exception as _pa_err:
    print(f"[presence] /api/next/presence disabled: {_pa_err.__class__.__name__}: {_pa_err}", flush=True)
# ---- END REMOTE CONTROL ----


@app.get("/api/health/ping")
def health_ping():
    return J({"ok": True, "t": int(time.time()), "uptime_s": int(time.time() - WATCHDOG.server_started_at),
              "bot_running": bool(BOT.running), "heartbeat": HEARTBEAT.status(), "live_publish": LIVEPUB.status()})


@app.get("/api/pc/doctor")
def pc_doctor_api(text: int = 0):
    """PC DOCTOR (tools/pc_doctor.py, tools/bat/PC_DOCTOR.bat): why the phone hears nothing from this PC, link by link. Read-only;
    never shows the private alert topic, a login or an account id. ?text=1 = the same card as plain text."""
    from tools import pc_doctor as _pd
    r = _pd.run(ping={"ok": True, "bot_running": bool(BOT.running), "heartbeat": HEARTBEAT.status()})
    if text:
        return Response(_pd.card_text(r), media_type="text/plain; charset=utf-8")
    return J(r)


@app.get("/api/health/watchdog")
def health_watchdog():
    st = WATCHDOG.status()
    h = BOT.health or {}
    st.update(bot_adapter=(BOT.cfg or {}).get("adapter"), data_age_s=h.get("data_age_s"), last_ok_poll=h.get("last_ok_poll"),
              last_error=h.get("last_error"), autostart_record=_wd.load(_AUTOSTART["path"]) is not None)
    return J(st)
# ---- END AUTOSTART ----


# ---- LAUNCH ----
# Launch Control page (web/js/page-launch.js). Live orders come from the TradingView Pine strategy through a webhook
# bridge (TradersPost / PickMyTrade) into the MFFU Tradovate account; this PC only mirrors it on paper. These routes
# report launch readiness and let the owner fire ONE sample entry at the bridge's PAPER webhook. The bridge URL is a
# credential: it is used for the single forward and never stored, logged or echoed back.
_LAUNCH_BLACKOUTS = os.path.join(ROOT, "tradingview", "blackouts.txt")


def _launch_sample():
    """Sample bridge entry: 1 MNQ buy, market, with stop and target near the last NQ price (or a placeholder)."""
    try:
        px = round(float(load("NQ", "5m").c[-1]) * 4) / 4
    except Exception:
        px = 25000.0
    return {"ticker": "MNQ1!", "action": "buy", "sentiment": "long", "quantity": 1, "orderType": "market",
            "price": px, "stopLoss": {"type": "stop", "stopPrice": px - 20.0}, "takeProfit": {"limitPrice": px + 40.0},
            "comment": "Liquidity Engine launch test (paper)", "test": True}


@app.get("/api/launch/blackouts")
def launch_blackouts(raw: int = 0):
    if not os.path.exists(_LAUNCH_BLACKOUTS):
        if raw:
            return Response("pending: tradingview/blackouts.txt has not been generated yet\n", media_type="text/plain; charset=utf-8")
        return J({"present": False, "status": "pending", "text": ""})
    with open(_LAUNCH_BLACKOUTS, encoding="utf-8", errors="replace") as fh:
        text = fh.read()[:20000]
    if raw:
        return Response(text, media_type="text/plain; charset=utf-8")
    rows = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    entries = []                         # the file may hold the same list twice (one line + one per line): de-duplicate
    for ln in rows:
        for e in ln.split(","):
            if e.strip() and e.strip() not in entries:
                entries.append(e.strip())
    return J({"present": True, "status": "ready", "text": text, "mtime": int(os.path.getmtime(_LAUNCH_BLACKOUTS)),
              "entries": entries, "compact": ",".join(entries), "lines": len(entries)})


@app.get("/api/launch/status")
def launch_status():
    sp = lambda *p: os.path.exists(os.path.join(ROOT, *p))
    try:
        auto_rec = _wd.load(_AUTOSTART["path"]) is not None
    except Exception:
        auto_rec = False
    task = None                          # Windows Task Scheduler task created by scripts/install_autostart.ps1
    if os.name == "nt":
        try:
            task = subprocess.run(["schtasks", "/Query", "/TN", "LiquidityEngine"], capture_output=True, timeout=5).returncode == 0
        except Exception:
            task = None
    return J({"server_time": int(time.time()), "status_ps1": sp("scripts", "status.ps1"), "run_bot_ps1": sp("scripts", "run_bot.ps1"),
              "install_ps1": sp("scripts", "install_autostart.ps1"), "autostart_record": auto_rec, "task_installed": task,
              "blackouts": sp("tradingview", "blackouts.txt"), "bridge_doc": sp("tradingview", "BRIDGE_SETUP.md"),
              "sample": _launch_sample()})


@app.post("/api/launch/test_webhook")
async def launch_test_webhook(req: Request):
    import urllib.error
    import urllib.parse
    import urllib.request
    try:
        body = await req.json()
    except Exception:
        return J({"ok": False, "error": "JSON body required"}, 400)
    url = str((body or {}).get("url") or "").strip()
    try:
        u = urllib.parse.urlsplit(url)
    except Exception:
        u = None
    if not u or u.scheme != "https" or not u.hostname or any(c in url for c in " \r\n\t"):
        return J({"ok": False, "error": "refused: the webhook URL must be a full https:// address"}, 400)
    payload = body.get("payload")
    if payload is None or payload == "":
        payload = _launch_sample()
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return J({"ok": False, "error": "payload is not valid JSON"}, 400)
    data = json.dumps(payload).encode()
    if len(data) > 8000:
        return J({"ok": False, "error": "payload too large (8 KB max)"}, 400)

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None                  # report a 3xx as-is instead of following it (could downgrade to http)

    opener = urllib.request.build_opener(_NoRedirect)
    rq = urllib.request.Request(url, data=data, method="POST",
                                headers={"Content-Type": "application/json", "User-Agent": "LiquidityEngine-launch-test/1"})
    t0 = time.time()
    try:
        with opener.open(rq, timeout=10) as resp:
            status, text = resp.status, resp.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            text = e.read(4000).decode("utf-8", "replace")
        except Exception:
            text = ""
        status = e.code
    except Exception as e:           # timeout / DNS / TLS: report the class + reason only, never the URL
        reason = getattr(e, "reason", None) or e
        msg = f"{e.__class__.__name__}: {reason}".replace(url, "<url>")
        return J({"ok": False, "status": None, "error": f"no response: {msg}"[:300], "elapsed_ms": int((time.time() - t0) * 1000),
                  "sent": payload})
    BOT._log("system", f"Launch test webhook sent to the bridge: HTTP {status}")    # URL deliberately not logged
    return J({"ok": 200 <= status < 300, "status": status, "body": text, "elapsed_ms": int((time.time() - t0) * 1000), "sent": payload})
# ---- END LAUNCH ----


# ---- CONFLUENCE SEARCH ----
# learning loop over every recorded confluence (engine/confluence_search.py): registry + background run with progress
_CSEARCH = {"proc": None, "started": None, "finished": None, "step": 0, "steps": 6, "msg": "", "lines": [], "rc": None}
_CSEARCH_LOCK = threading.Lock()


def _csearch_reader(proc):
    for raw in iter(proc.stdout.readline, ""):
        line = raw.rstrip()
        with _CSEARCH_LOCK:
            if line.startswith("PROGRESS "):
                try:
                    frac, msg = line[9:].split(" ", 1)
                    a, b = frac.split("/")
                    _CSEARCH.update(step=int(a), steps=int(b), msg=msg)
                except ValueError:
                    pass
            elif line:
                _CSEARCH["lines"] = (_CSEARCH["lines"] + [line])[-40:]
    proc.wait()
    with _CSEARCH_LOCK:
        _CSEARCH.update(finished=time.time(), rc=proc.returncode,
                        msg="done" if proc.returncode == 0 else f"failed (exit {proc.returncode})")


def _csearch_running():
    return _CSEARCH["proc"] is not None and _CSEARCH["proc"].poll() is None


@app.get("/api/confluence/registry")
def api_confluence_registry():
    """The confluence registry (ACTIVE / PROBATION / CANDIDATE / RETIRED with per-fold evidence and the last run)."""
    path = os.path.join(ROOT, "data", "confluence_registry.json")
    data = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as e:
            return J({"running": _csearch_running(), "data": None, "error": f"registry unreadable: {e}"})
    return J({"running": _csearch_running(), "data": data})


@app.post("/api/confluence/run")
def api_confluence_run():
    """Start one learning cycle in the background (python -m engine.confluence_search --run)."""
    with _CSEARCH_LOCK:
        if _csearch_running():
            return J({"running": True, "already": True})
        proc = subprocess.Popen([sys.executable, "-u", "-m", "engine.confluence_search", "--run"], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        _CSEARCH.update(proc=proc, started=time.time(), finished=None, step=0, steps=6, msg="starting", lines=[], rc=None)
    threading.Thread(target=_csearch_reader, args=(proc,), daemon=True).start()
    return J({"running": True})


@app.get("/api/confluence/status")
def api_confluence_status():
    with _CSEARCH_LOCK:
        s = {k: v for k, v in _CSEARCH.items() if k != "proc"}
    s["running"] = _csearch_running()
    s["elapsed_s"] = None if not s["started"] else round((s["finished"] or time.time()) - s["started"], 1)
    return J(s)
# ---- END CONFLUENCE SEARCH ----


# ---- DASH EXTRAS ----
# /api/dash/*: read-only dashboard analytics (engine/dash_*.py, contract in research/DASHBOARD_API.md). Backtests run in a
# below-normal-priority subprocess; an import failure here is logged and never stops the server or the bot.
try:
    from engine import dash_api as _dash
    _dash.bind(watchdog=WATCHDOG, live_arm=_live_arm)
    app.include_router(_dash.router)
    app.router.add_event_handler("startup", _dash.startup)
except Exception as _dash_err:
    print(f"[dash] /api/dash disabled: {_dash_err.__class__.__name__}: {_dash_err}", flush=True)
# ---- END DASH EXTRAS ----


# Dashboard UI: web_next/ (the redesigned command center) is served first and falls back to web/ for every file it does
# not override, so all page modules are shared. LE_UI=classic serves the old web/ dashboard unchanged.
WEB_NEXT = os.path.join(ROOT, "web_next")
UI_DIRS = [WEB] if os.environ.get("LE_UI", "next") == "classic" or not os.path.isdir(WEB_NEXT) else [WEB_NEXT, WEB]


@app.get("/")
def index():
    return FileResponse(os.path.join(UI_DIRS[0], "index.html"))


from engine.extras_api import router as extras_router; app.include_router(extras_router)
from engine.next_api import router as next_router; app.include_router(next_router)
from engine.insight_api import router as insight_router; app.include_router(insight_router)   # AI Insights page (read-only GET /api/next/insight)
from engine.liveview_api import router as liveview_router; app.include_router(liveview_router)   # Live View page (read-only GET /api/next/liveview)
from engine.holo_api import router as holo_router; app.include_router(holo_router)   # Holodeck (read-only GET /api/next/holo, /api/next/holo/days)
from engine.mind import router as mind_router; app.include_router(mind_router)   # Mind (read-only GET /api/next/mind: regime, plans, similar setups, reviews, proposals)
# the PC pages' LIT backtest (/api/next/lit_backtest: LIT replay + levels / session boxes of every 2026 day, ~5-25 s) is built
# in the background at start, so the first dashboard load does not wait for it (LE_PREWARM=0 skips it)
if os.environ.get("LE_PREWARM", "1") != "0":
    def _prewarm_lit():
        try:
            from engine import lit_dash
            lit_dash.backtest("2026")
        except Exception as e:
            print(f"[lit_dash] prewarm failed: {e}")
    threading.Thread(target=_prewarm_lit, name="lit-prewarm", daemon=True).start()
# ---- LIVE SITE ---- (engine/live_site.py, docs/LIVE_DASHBOARD.md): the whole phone site at /site/ (the Gate, the dashboard, every
# OLYMPUS app) with the bot's live numbers, for the private Tailscale link (tools/bat/LIVE_LINK.bat). Read-only over the link: a proxied
# request may only GET / HEAD (POST etc. refused before any route), Funnel refused. Before the static mount: its routes win.
try:
    from engine import live_site as _ls
    _ls.install(app, live=LIVEPUB.payload)
except Exception as _ls_err:
    print(f"[live_site] /site disabled: {_ls_err.__class__.__name__}: {_ls_err}", flush=True)
# ---- END LIVE SITE ----
# ---- DAY INBOX ---- (engine/day_inbox.py, docs/CONNECT_DAY.md): POST /inbox/{kind} only appends one line to data/inbox/<kind>.jsonl
# (the iPhone "Add to my day" Shortcut over the private Tailscale link); never trading. Registered kinds only; Funnel refused.
try:
    from engine import day_inbox as _di
    _di.install(app)
except Exception as _di_err:
    print(f"[day_inbox] disabled: {_di_err.__class__.__name__}: {_di_err}", flush=True)
# ---- END DAY INBOX ----
# ---- ZEUS PHONE SAFETY ---- (engine/phone_safety.py, docs/ZEUS_FEATURES.md): /safety/ = PAUSE / RESUME / FLATTEN / KILL from the
# phone over the private Tailscale link only, through REMOTE's own command code. OFF until `python -X utf8 -m engine.phone_safety --on`.
# Never start / arm / update: no such button.
try:
    from engine import phone_safety as _ps
    _ps.install(app, REMOTE, BOT)
except Exception as _ps_err:
    print(f"[phone_safety] /safety disabled: {_ps_err.__class__.__name__}: {_ps_err}", flush=True)
# ---- END ZEUS PHONE SAFETY ----
# ---- ADD ACCOUNT BOX ---- (engine/account_box.py): /add-account/ = pick the plan + type the NinjaTrader Name, the same checks as
# ADD_ACCOUNT.bat (engine/account_cli.add). PC itself or the private Tailscale link only, same-origin, never arms.
try:
    from engine import account_box as _ab
    _ab.install(app)
except Exception as _ab_err:
    print(f"[account_box] /add-account disabled: {_ab_err.__class__.__name__}: {_ab_err}", flush=True)
# ---- END ADD ACCOUNT BOX ----
# ---- PHONE ALERTS BOX ---- (engine/alerts_box.py, docs/ALERTS.md): /alerts/ = ALERTS_SETUP option 1 (Telegram) from the phone: paste
# the BotFather token, tap START in the bot, test delivered. PC itself or the private Tailscale link only, same-origin, never trading.
try:
    from engine import alerts_box as _alb
    _alb.install(app)
except Exception as _alb_err:
    print(f"[alerts_box] /alerts disabled: {_alb_err.__class__.__name__}: {_alb_err}", flush=True)
# ---- END PHONE ALERTS BOX ----
_static = StaticFiles(directory=WEB)
_static.all_directories = list(UI_DIRS)       # first directory that has the file wins
app.mount("/", _static, name="web")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    host = os.environ.get("HOST", "0.0.0.0")     # reachable from your phone on the LAN / Tailscale; set HOST=127.0.0.1 to keep it local
    print(f"NQ Liquidity Bot dashboard -> http://127.0.0.1:{port}  (phone: Settings > Open on your phone)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
