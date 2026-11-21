"""ZEUS phone safety switch: PAUSE / RESUME / FLATTEN / KILL from the iPhone in one tap, over the owner's PRIVATE Tailscale link
only (owner 2026-11-18: "YES to a phone PAUSE + FLATTEN button, private Tailscale link only, can never arm"). docs/ZEUS_FEATURES.md.

Why: the old phone remote (engine/remote_ctl.py) reads a GitHub branch, and GitHub is gone (engine/nogithub.py), so today the
phone can only WATCH the bot (engine/live_site.py: read-only over the link). This adds four buttons, nothing more:

  pause    no NEW entries until the next 4 PM ET (pressed in the day: the rest of this session; at night: all of the next
           one; or {"until": "HH:MM" | "tomorrow"}); an open trade keeps its stop / target
           (engine/entry_pause.py, checked by engine/guards for LIT, the extra accounts and ATLAS)
  resume   lift that pause (it never starts a stopped bot, never undoes a flatten's "no new entry today")
  flatten  close every open position of the bot now (BOT.flatten_now: LIT, extra accounts, ATLAS); the bot keeps running,
           no new entry until the next trading day
  kill     HOLD TO KILL: flatten everything (NinjaTrader FLATTENEVERYTHING), stop the bot, auto-resume OFF. Starting again is
           done at the PC with the typed live phrase, as always

Never: start, arm, update, restart, size, settings. There is no code path from here to any of them (ACTIONS is the whole list,
each runs the SAME function the GitHub remote runs: RemoteControl.run_cmd, with its log, hands-off record and phone notice).
Kalshi (2026-11-19): every press also reaches the Kalshi live executor when it is ON (engine/kalshi_live.phone_press: pause /
resume / flatten / kill, its own words appended to the answer; nothing when it is OFF); it can never switch Kalshi on.

Who may press (every check must pass; check() is pure, the tests call it):
  1 switched ON at the PC (OFF by default, it acts on orders): python -X utf8 -m engine.phone_safety --on
    (data/phone_safety.json, gitignored; LE_PHONE_SAFETY=0 forces it off, =1 on)
  2 the PC itself or the owner's Tailscale link (engine/live_site.private_why: a tailnet address, a signed-in
    Tailscale-User-Login, Host <pc>.<tailnet>.ts.net); refused: another device on the home WiFi, Tailscale Funnel
    (internet), any other tunnel. Public ntfy is never a way in (nothing here reads ntfy)
  3 sent by this page itself: header X-Zeus-Safety: 1 + JSON body (a page on another site cannot add that header without a
    CORS preflight this server never approves), Origin = this host, Sec-Fetch-Site not cross-site
  4 {"confirm": "<action>"} in the body equals the action (the page's second tap for flatten / kill)
  5 at most 8 presses in 10 minutes
Every press (allowed or refused) is one line in data/phone_safety_log.jsonl (no account id, no secret).

Routes (server.py: install(app, REMOTE, BOT) after live_site / day_inbox, before the static mount):
  GET  /safety/          the one-screen page (inline: works without the site build, no service worker)
  GET  /safety/status    {on, running, position, others_open, pause, no_entries_today, kill, last, trail}
  POST /safety/<action>  pause | resume | flatten | kill
Tests: python -X utf8 -m tests.test_phone_safety
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import urllib.parse

try:                                    # module level: the route signatures below are resolved by name (postponed annotations)
    from fastapi import Request
except Exception:  # noqa: BLE001
    Request = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "phone_safety.json")
LOG_PATH = os.path.join(ROOT, "data", "phone_safety_log.jsonl")
PREFIX = "/safety"
HEADER = "x-zeus-safety"
ACTIONS = {"pause": "pause", "resume": "resume_entries", "flatten": "flatten", "kill": "kill"}   # page action -> remote cmd
NEVER = ("start", "arm", "update", "restart", "settings", "size")
RATE_N, RATE_S = 8, 600
MAX_BODY = 512
HOW_ON = "python -X utf8 -m engine.phone_safety --on"
PAUSE_UNTIL = "16:00"        # the next 4 PM ET: pressed in the day = the rest of this session, at night = all of the next one
_S: dict = {"rc": None, "bot": None, "installed": False}
_LOCK = threading.Lock()
_HITS: list = []


# ------------------------------------------------------------------------------------------------ on / off
def _env(env=None):
    return os.environ if env is None else env


def is_on(env=None, path: str | None = None) -> bool:
    path = path or STATE_PATH
    v = str(_env(env).get("LE_PHONE_SAFETY", "")).strip()
    if v == "0":
        return False
    if v == "1":
        return True
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("on") is True
    except Exception:  # noqa: BLE001
        return False


def set_on(on: bool, path: str | None = None, now=None) -> dict:
    path = path or STATE_PATH
    rec = {"on": bool(on), "t": int(time.time() if now is None else now), "by": "pc"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    return rec


# ------------------------------------------------------------------------------------------------ the checks (pure)
def _h(headers) -> dict:
    return {str(k).lower(): str(v) for k, v in (headers.items() if hasattr(headers, "items") else [])}


def link_why(client, headers) -> str | None:
    """None = the PC itself or the owner's Tailscale link; else why not (engine/live_site.private_why)."""
    try:
        from engine import live_site
        return live_site.private_why(client, headers)
    except Exception:  # noqa: BLE001
        return "private: the link check could not run"


def origin_why(headers) -> str | None:
    """None = sent by this page (same origin); else why not."""
    h = _h(headers)
    if h.get(HEADER, "").strip() != "1":
        return "not sent by the ZEUS safety page (open /safety/ on your phone)"
    if "json" not in h.get("content-type", "").lower():
        return "not sent by the ZEUS safety page (JSON only)"
    if h.get("sec-fetch-site", "same-origin").strip().lower() not in ("same-origin", "none"):
        return "refused: sent from another site"
    o = h.get("origin", "").strip()
    if not o:
        return "refused: no Origin (open /safety/ on your phone)"
    host = h.get("x-forwarded-host") or h.get("host") or ""
    if urllib.parse.urlsplit(o).netloc.lower() != host.strip().lower():
        return "refused: sent from another site"
    return None


def body_why(action: str, body) -> str | None:
    if not isinstance(body, dict):
        return "the body must be JSON"
    if str(body.get("confirm") or "") != action:
        return f"not confirmed: tap {action.upper()} again"
    if action == "pause" and body.get("until") not in (None, "", "tomorrow", PAUSE_UNTIL):
        if not isinstance(body.get("until"), str) or len(body["until"]) > 10:
            return "pause until: HH:MM or tomorrow"
    return None


def _rate_ok(now: float) -> bool:
    with _LOCK:
        while _HITS and now - _HITS[0] > RATE_S:
            _HITS.pop(0)
        if len(_HITS) >= RATE_N:
            return False
        _HITS.append(now)
        return True


def check(action: str, raw: bytes, headers, client, env=None, now=None, state_path: str | None = None) -> tuple:
    """(None, body) = may run; else (http status, reply). Order: known action, on, private link, same page, body, rate."""
    now = time.time() if now is None else now
    if action not in ACTIONS:
        return 404, {"ok": False, "error": f"no such button (only {', '.join(ACTIONS)}; start / arm stay on the PC)"}
    if not is_on(env, state_path):
        return 403, {"ok": False, "error": f"the phone safety switch is OFF. Turn it on once at the PC: {HOW_ON}"}
    why = link_why(client, headers)
    if why:
        return 403, {"ok": False, "error": why}
    if _h(headers).get("tailscale-funnel-request"):
        return 403, {"ok": False, "error": "private: never from the internet"}
    why = origin_why(headers)
    if why:
        return 403, {"ok": False, "error": why}
    if raw is None or len(raw) > MAX_BODY:
        return 413, {"ok": False, "error": "too long"}
    try:
        body = json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
    except (ValueError, RecursionError):
        return 400, {"ok": False, "error": "that is not JSON"}
    why = body_why(action, body)
    if why:
        return 400, {"ok": False, "error": why}
    if not _rate_ok(now):
        return 429, {"ok": False, "error": "too many taps in a row: wait a few minutes (or use NinjaTrader / the MFFU app)"}
    return None, body


def allowed(method: str, path: str) -> bool:
    """engine/live_site.guard asks this: the only POSTs the phone link may make here (once install() ran)."""
    p = str(path or "")
    return bool(_S["installed"] and (method or "").upper() == "POST" and p.startswith(PREFIX + "/")
                and p[len(PREFIX) + 1:] in ACTIONS)


# ------------------------------------------------------------------------------------------------ running a press
def log(row: dict, path: str | None = None):
    path = path or LOG_PATH
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:  # noqa: BLE001
        pass


def recent(n: int = 5, path: str | None = None) -> list:
    path = path or LOG_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh.read().splitlines()[-200:] if x.strip()]
    except Exception:  # noqa: BLE001
        return []
    return rows[-n:]


def run(rc, action: str, body: dict, now=None, log_path: str | None = None) -> dict:
    """One press through the remote control's own command code (rc: engine/remote_ctl.RemoteControl)."""
    from engine import remote_ctl
    now = time.time() if now is None else now
    cmd = ACTIONS[action]
    assert cmd not in NEVER
    cid = f"phone-{int(now)}-{secrets.token_hex(3)}"
    c = {"id": cid, "ts": int(now), "cmd": cmd}
    if cmd == "pause":
        c["until"] = body.get("until") or PAUSE_UNTIL
    with _LOCK:
        d = remote_ctl.load_done(rc.done_path)
        d.setdefault("done", {})[cid] = {"cmd": cmd, "t": int(now), "status": "running", "msg": ""}
        remote_ctl.save_done(d, rc.done_path)
        try:
            status, msg = rc.run_cmd(c, d, now)
        except Exception as e:  # noqa: BLE001
            status, msg = "failed", f"{e.__class__.__name__}: {e}: use NinjaTrader / the MFFU app NOW"
        if status not in ("done", "refused", "failed"):
            status = "failed"
        rc._finish(d, cid, cmd, status, msg, now, title=f"Phone {action.upper()}: {status}")
    try:                                    # the same press for the Kalshi live executor (engine/kalshi_live.py); '' when it is OFF
        from engine import kalshi_live
        k = kalshi_live.phone_press(action, now=now)
        if k:
            msg = f"{msg} | {k}"
    except Exception:  # noqa: BLE001
        pass
    row = {"t": int(now), "action": action, "status": status, "msg": str(msg)[:200], "src": "phone"}
    log(row, log_path)
    try:
        rc._hook("beat")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": status == "done", "status": status, "said": str(msg)[:300], "action": action}


def status_view(bot, env=None, now=None, state_path: str | None = None, log_path: str | None = None) -> dict:
    """What the page shows. No account id, no secret."""
    now = time.time() if now is None else now
    out = {"ok": True, "on": is_on(env, state_path), "how_on": HOW_ON, "t": int(now), "running": bool(getattr(bot, "running", False)),
           "kill": bool(getattr(bot, "kill", False)), "position": "flat", "others_open": 0, "pause": None,
           "no_entries_today": False, "last": recent(5, log_path)}
    st = getattr(bot, "state", None) or {}
    pos = st.get("position")
    if isinstance(pos, dict) and pos:
        out["position"] = f"{'LONG' if pos.get('dir') == 1 else 'SHORT'} {pos.get('qty') or '?'}"
    n = 0
    try:
        for acc in list(getattr(getattr(bot, "accts", None), "accounts", None) or []):
            n += getattr(acc, "open_t", None) is not None
        for name in ("acct_b", "acct_r", "acct_r2"):
            a = getattr(bot, name, None)
            n += a is not None and getattr(a, "open_t", None) is not None
    except Exception:  # noqa: BLE001
        pass
    out["others_open"] = int(n)
    try:
        from engine import entry_pause
        p = entry_pause.active(now, entry_pause.path_for(bot) if getattr(bot, "state_path", None) else entry_pause.PATH)
        out["pause"] = p.get("label") if p else None
    except Exception:  # noqa: BLE001
        pass
    try:
        from engine.live import trading_day
        out["no_entries_today"] = getattr(bot, "_no_entries_day", None) == trading_day(now)
    except Exception:  # noqa: BLE001
        pass
    try:
        from engine import audit_trail
        out["trail"] = audit_trail.recent(8, now=now)
    except Exception:  # noqa: BLE001
        out["trail"] = []
    try:                                    # Kalshi live executor: one short line, None when it is OFF
        from engine import kalshi_live
        out["kalshi"] = kalshi_live.phone_view(now=now)
    except Exception:  # noqa: BLE001
        out["kalshi"] = None
    return out


# ------------------------------------------------------------------------------------------------ the page
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>ZEUS Safety</title>
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="ZEUS Safety">
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#111;--mute:#5b6470;--line:#dde1e6;--warn:#b45309;--bad:#b91c1c;--ok:#15803d;--btn:#1f2937}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--mute:#9aa4ae;--line:#30363d;--btn:#e6edf3}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.4 -apple-system,system-ui,sans-serif;
padding:16px;padding-top:max(16px,env(safe-area-inset-top))}main{max-width:480px;margin:0 auto}
h1{font-size:22px;margin:4px 0 12px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:0 0 12px}
.row{display:flex;justify-content:space-between;gap:8px;padding:3px 0}.mute{color:var(--mute);font-size:14px}
button{width:100%;font:600 18px/1 inherit;padding:18px;border-radius:12px;border:2px solid var(--line);background:var(--card);
color:var(--ink);margin:0 0 10px;cursor:pointer}button.warn{border-color:var(--warn);color:var(--warn)}
button.bad{border-color:var(--bad);color:var(--bad)}button.primed{background:var(--bad);color:#fff;border-color:var(--bad)}
button:disabled{opacity:.45}#said{min-height:1.4em;font-weight:600}.off{color:var(--bad);font-weight:600}
ul{margin:6px 0 0;padding-left:18px}li{margin:2px 0;font-size:14px}
</style></head><body><main>
<h1>ZEUS Safety</h1>
<div class="card" id="st"><div class="mute">Loading...</div></div>
<div id="said" class="card" hidden></div>
<button id="b-pause" class="warn">PAUSE new trades until 4 PM ET</button>
<button id="b-resume">RESUME new trades</button>
<button id="b-flatten" class="bad">FLATTEN all now</button>
<button id="b-kill" class="bad">KILL: flatten all + stop the bot</button>
<p class="mute">Your own devices on Tailscale only. This page can pause, flatten or stop ZEUS. It can never start or arm it:
that stays on the PC with the typed phrase. FLATTEN and KILL need a second tap. If this page does not answer, close the trade
in NinjaTrader or the MFFU app.</p>
<div class="card"><b>What happened</b><ul id="trail"><li class="mute">-</li></ul></div>
<p class="mute"><a href="/kalshi-live/">Kalshi K8 (key, bet size, start / STOP)</a></p>
<p class="mute"><a href="/alerts/">Phone alerts (Telegram setup + test)</a></p>
</main><script>
var primed=null,timer=null,ON=false;
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function hm(t){var d=new Date(t*1000);return d.toLocaleString([], {weekday:"short",hour:"2-digit",minute:"2-digit"})}
function say(t){var e=document.getElementById("said");e.hidden=!t;e.textContent=t||""}
function load(){fetch("status",{cache:"no-store"}).then(function(r){return r.json()}).then(function(s){
 ON=!!s.on;var h="";
 if(!s.ok){h='<div class="off">'+esc(s.error||"not available")+'</div>'}
 else{
  if(!s.on)h+='<div class="off">Switch is OFF. Turn it on once at the PC:<br><code>'+esc(s.how_on)+'</code></div>';
  h+='<div class="row"><span>Bot</span><b>'+(s.running?"RUNNING":"STOPPED")+(s.kill?" (KILL on)":"")+'</b></div>';
  h+='<div class="row"><span>Zlarior position</span><b>'+esc(s.position)+'</b></div>';
  h+='<div class="row"><span>Other accounts open</span><b>'+esc(s.others_open)+'</b></div>';
  h+='<div class="row"><span>New trades</span><b>'+(s.pause?"PAUSED until "+esc(s.pause):(s.no_entries_today?"blocked today (flattened)":"allowed"))+'</b></div>';
  if(s.kalshi)h+='<div class="row"><span>Kalshi</span><b>'+esc(s.kalshi)+'</b></div>';
  h+='<div class="mute">Updated '+hm(s.t)+'</div>';
  var tr=(s.trail||[]).slice().reverse().map(function(x){return "<li>"+esc(hm(x.t))+" &middot; "+esc(x.what)+"</li>"}).join("");
  document.getElementById("trail").innerHTML=tr||'<li class="mute">nothing yet</li>';
 }
 document.getElementById("st").innerHTML=h;
 ["pause","resume","flatten","kill"].forEach(function(a){document.getElementById("b-"+a).disabled=!s.ok||!s.on});
}).catch(function(){document.getElementById("st").innerHTML='<div class="off">The PC does not answer. Close the trade in NinjaTrader or the MFFU app.</div>'})}
function send(a){
 var b=document.getElementById("b-"+a);b.disabled=true;say("Sending "+a.toUpperCase()+"...");
 fetch(a,{method:"POST",headers:{"Content-Type":"application/json","X-Zeus-Safety":"1"},body:JSON.stringify({confirm:a})})
 .then(function(r){return r.json()}).then(function(j){say((j.ok?"DONE: ":"NOT DONE: ")+(j.said||j.error||""));load()})
 .catch(function(){say("NOT SENT: the PC does not answer. Use NinjaTrader or the MFFU app.")}).then(function(){b.disabled=!ON})}
function tap(a,two){var b=document.getElementById("b-"+a);
 if(!two){send(a);return}
 if(primed===a){clearTimeout(timer);primed=null;b.classList.remove("primed");b.textContent=b.dataset.t;send(a);return}
 if(primed){var o=document.getElementById("b-"+primed);o.classList.remove("primed");o.textContent=o.dataset.t}
 primed=a;b.dataset.t=b.textContent;b.textContent="Tap again to "+a.toUpperCase();b.classList.add("primed");
 timer=setTimeout(function(){primed=null;b.classList.remove("primed");b.textContent=b.dataset.t},4000)}
document.getElementById("b-pause").onclick=function(){tap("pause",false)};
document.getElementById("b-resume").onclick=function(){tap("resume",false)};
document.getElementById("b-flatten").onclick=function(){tap("flatten",true)};
document.getElementById("b-kill").onclick=function(){tap("kill",true)};
load();setInterval(load,10000);
</script></body></html>"""


# ------------------------------------------------------------------------------------------------ wiring
def install(app, rc, bot) -> dict:
    """GET /safety/, GET /safety/status, POST /safety/<action>; tells live_site's read-only guard these POSTs may pass."""
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

    _S.update(rc=rc, bot=bot)
    nostore = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}

    def _client(request) -> str:
        return getattr(getattr(request, "client", None), "host", None) or ""

    @app.get(PREFIX)
    def r_safety_root():
        return RedirectResponse(PREFIX + "/", status_code=307)

    @app.get(PREFIX + "/")
    def r_safety_page(request: Request):
        why = link_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        return HTMLResponse(PAGE, headers={**nostore, "Content-Security-Policy":
                                           "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                                           "connect-src 'self'; frame-ancestors 'none'"})

    @app.get(PREFIX + "/status")
    def r_safety_status(request: Request):
        why = link_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        return JSONResponse(status_view(_S["bot"]), headers=nostore)

    @app.post(PREFIX + "/{action}")
    async def r_safety_press(action: str, request: Request):
        raw = b""
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > MAX_BODY:
                break
        code, body = check(action, raw, request.headers, _client(request))
        if code is not None:
            log({"t": int(time.time()), "action": str(action)[:20], "status": "refused", "msg": str(body.get("error"))[:200],
                 "src": "phone"})
            return JSONResponse(body, status_code=code, headers=nostore)
        out = run(_S["rc"], action, body)
        return JSONResponse(out, status_code=200, headers=nostore)

    _S["installed"] = True
    try:
        from engine import live_site
        live_site.allow_post(allowed)
    except Exception:  # noqa: BLE001
        pass
    try:                                    # the Kalshi K8 phone page (/kalshi-live/, engine/kalshi_web.py): same private link, never the futures bot
        from engine import kalshi_web
        kalshi_web.install(app)
    except Exception:  # noqa: BLE001
        pass
    return {"actions": sorted(ACTIONS), "on": is_on()}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ZEUS phone safety switch (pause / flatten / kill from the phone, Tailscale only)")
    ap.add_argument("--on", action="store_true", help="turn the phone buttons on (run this at the PC)")
    ap.add_argument("--off", action="store_true", help="turn them off")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    if a.on or a.off:
        set_on(bool(a.on))
    on = is_on()
    print(f"ZEUS phone safety: {'ON' if on else 'OFF'}. Phone page: https://<this-pc>.<tailnet>.ts.net/safety/ "
          f"(LIVE_LINK.bat prints the address). Buttons: pause, resume, flatten, kill. It can never start or arm.")
    if not on:
        print(f"Turn on: {HOW_ON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
