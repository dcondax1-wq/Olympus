"""Phone alerts box (owner 2026-11-21, from his iPhone: "Give me a way to setup phone alerts with just my phone quickly").

ALERTS_SETUP.bat option 1 (Telegram) as ONE private page on the PC bot server, so the BotFather token is pasted on the PHONE, not
at the PC: http://localhost:8766/alerts/ on the PC, https://<pc>.<tailnet>.ts.net:8444/alerts/ on the phone (engine/phone_link.py;
:443 is the owner's old Jarvis app). Modelled exactly on engine/account_box.py (/add-account/): the same guards, the same install.

  GET  /alerts/          the page: the BotFather steps, a hidden token box + Connect, then "Open @<bot> and tap START"
  GET  /alerts/status    state words + booleans only: never the token, the chat id or the bot's name
  POST /alerts/connect   {"token"}: the format (alert_bus.good_token), then Telegram getMe (alert_bus._http, the bus's own HTTP
                         helper) for the bot's username. A background thread then waits up to 3 minutes for the owner's /start
                         (tools/alerts_setup.wait_chat_id), runs tools/alerts_setup.setup_telegram itself (the Telegram test
                         "Olympus alerts are ON") and, delivered, saves {"telegram": {token, chat_id, on}} with
                         alerts_setup.save_raw exactly as ALERTS_SETUP option 1 does (not delivered = nothing saved, as there),
                         then the bus on as ALERTS_ON does (alerts_setup.switch(True): only when ALERTS_OFF had switched it off)
  POST /alerts/cancel    {} drop the wait (nothing saved)
  POST /alerts/test      {} TEST_ALERT.bat: the test alert through every channel; the reply is {channel: true / false} only

Every POST must pass check(): not cloud mode; the private link (engine/live_site.private_why: the PC itself, or a device signed in
to the owner's tailnet; never the home WiFi, never Funnel / another tunnel); sent by this page (X-Olympus-Alerts: 1 header, JSON,
Sec-Fetch-Site same-origin, Origin = Host, so another web site cannot press it); body <= 512 bytes; at most 8 presses in 10 minutes.
THE TOKEN IS A SECRET: never logged, echoed, put in a status, a reply or an exception text; it lives only in the wait thread's
memory until saved in %USERPROFILE%\\.olympus\\alerts.json (never the repo). Every press is one line in data/alerts_box.jsonl
(gitignored): action, ok, a reason word, the bot's username masked. Read-only for trading: nothing here places, changes or arms.
Tests: python -X utf8 -m tests.test_alerts_box
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
import urllib.parse

try:                                    # module level: route signatures are resolved by name
    from fastapi import Request
except Exception:  # noqa: BLE001
    Request = None

from engine import alert_bus as AB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "/alerts"
ACTIONS = ("connect", "cancel", "test")
HEADER = "x-olympus-alerts"
MAX_BODY = 512
RATE_N, RATE_S = 8, 600
WAIT_S = 180                            # tools/alerts_setup.WAIT_S: up to 3 minutes for the owner's /start
GETME_TIMEOUT_S = 15
_USER_RX = re.compile(r"[A-Za-z][A-Za-z0-9_]{3,31}")
_S: dict = {"installed": False, "log": None, "wait_s": WAIT_S, "sleep": time.sleep}
_W: dict = {"state": "idle", "reason": None, "test_delivered": None, "gen": 0, "t0": None}
_LOCK = threading.Lock()
_HITS: list = []

# reason word -> (what happened, the one fix). The page shows these; the status sends only the word.
REASONS = {
    "bad_format": ("That is not a BotFather token.",
                   "In BotFather long-press the whole token (numbers, a colon, then letters) -> Copy, then paste it here again."),
    "token_refused": ("Telegram says that token is wrong.",
                      "Copy the token again from BotFather (gone? send /mybots -> your bot -> API Token), paste, Connect."),
    "no_internet": ("The PC could not reach Telegram.", "Check the PC's internet, then tap Connect again."),
    "telegram_error": ("Telegram did not answer properly.", "Wait a minute, then tap Connect again."),
    "no_start": ("No START seen in 3 minutes. Nothing saved.",
                 "Tap Connect again, then tap the Open button and START in your bot within 3 minutes."),
    "test_failed": ("Telegram did not deliver the test message, so nothing was saved.",
                    "Tap Connect again. Fails twice? Double-click ALERTS_SETUP.bat on the PC once."),
    "save_failed": ("The test arrived but the PC could not save the setup.", "Double-click ALERTS_SETUP.bat on the PC once."),
    "bus_off": ("Saved and tested, but the alert bus is switched off on this PC.", "Double-click ALERTS_ON.bat on the PC."),
    "cancelled": ("Stopped. Nothing saved.", "Tap Connect to start again."),
    "failed": ("It did not run on the PC. Nothing saved.", "Double-click ALERTS_SETUP.bat on the PC once."),
}


def _now() -> float:
    return time.time()


def mask_bot(user) -> str:
    """The bot's username for the log: the first 2 letters + the last 3 ("ol…bot"), never the whole name."""
    u = str(user or "").strip().lstrip("@")
    return "" if not u else ("@" + u[:2] + "…" + u[-3:] if len(u) > 5 else "@…")


def log(row: dict) -> None:
    path = _S["log"] or os.path.join(ROOT, "data", "alerts_box.jsonl")
    try:
        line = AB.redact(json.dumps(row, separators=(",", ":"), ensure_ascii=False))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def _rate_ok(now) -> bool:
    with _LOCK:
        while _HITS and now - _HITS[0] > RATE_S:
            _HITS.pop(0)
        if len(_HITS) >= RATE_N:
            return False
        _HITS.append(now)
        return True


def _h(headers) -> dict:
    return {str(k).lower(): str(v) for k, v in (headers.items() if hasattr(headers, "items") else [])}


def link_why(client, headers) -> str | None:
    """None = the PC itself or the owner's Tailscale link (engine/live_site.private_why); else why not."""
    if os.environ.get("LE_CLOUD") == "1":
        return "cloud mode: phone alerts are set up on the PC"
    try:
        from engine import live_site
        return live_site.private_why(client, headers)
    except Exception:  # noqa: BLE001
        return "private: the link check could not run"


def origin_why(headers) -> str | None:
    """None = sent by this page (same origin); else why not."""
    h = _h(headers)
    if h.get(HEADER, "").strip() != "1":
        return "not sent by the Phone alerts page (open /alerts/)"
    if "json" not in h.get("content-type", "").lower():
        return "not sent by the Phone alerts page (JSON only)"
    if h.get("sec-fetch-site", "same-origin").strip().lower() not in ("same-origin", "none"):
        return "refused: sent from another site"
    o = h.get("origin", "").strip()
    if not o:
        return "refused: no Origin (open /alerts/)"
    host = h.get("x-forwarded-host") or h.get("host") or ""
    if urllib.parse.urlsplit(o).netloc.lower() != host.strip().lower():
        return "refused: sent from another site"
    return None


def check(action, raw, headers, client, now=None) -> tuple:
    """(None, body) = may run; else (http status, reply). Never echoes the body."""
    now = _now() if now is None else now
    if action not in ACTIONS:
        return 404, {"ok": False, "error": "no such button"}
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
    if not isinstance(body, dict):
        return 400, {"ok": False, "error": "that is not JSON"}
    if not _rate_ok(now):
        return 429, {"ok": False, "error": "too many taps in a row: wait a few minutes"}
    return None, body


def allowed(method: str, path: str) -> bool:
    """engine/live_site.guard asks this: the only POSTs this page may make over the Tailscale link."""
    p = str(path or "")
    return bool(_S["installed"] and (method or "").upper() == "POST" and p.startswith(PREFIX + "/") and p[len(PREFIX) + 1:] in ACTIONS)


# ------------------------------------------------------------------------------------------------ the work (tools/alerts_setup)
def _setup():
    from tools import alerts_setup
    return alerts_setup


def _set(gen=None, **kw) -> bool:
    """Update the wait state; with gen, only while that wait is still the current one."""
    with _LOCK:
        if gen is not None and _W["gen"] != gen:
            return False
        _W.update(**kw)
        return True


def get_me(token: str) -> tuple:
    """(username | None, reason word | None) from Telegram getMe, through alert_bus's own HTTP helper. The token goes only in
    the URL to api.telegram.org; nothing it raises or answers is passed on (only a reason word)."""
    try:
        st, txt = AB._http("GET", f"{AB.TG_API}/bot{token}/getMe", None, {}, GETME_TIMEOUT_S)
    except Exception:  # noqa: BLE001
        return None, "no_internet"
    j = AB._json(txt)
    if st in (401, 404):
        return None, "token_refused"
    if not st:
        return None, "no_internet"
    user = str(AB._d(j.get("result")).get("username") or "")
    if st != 200 or not j.get("ok") or not _USER_RX.fullmatch(user):
        return None, "telegram_error"
    return user, None


def _wait_and_save(token: str, gen: int, code: str | None = None) -> dict:
    """The background half of Connect: ALERTS_SETUP option 1 from the /start on. -> {"state", "reason", "test_delivered"}."""
    S = _setup()
    seen = {"wrong": False, "chat": False}

    def live() -> bool:
        return _W["gen"] == gen

    def clock() -> float:                 # a dropped wait ends wait_chat_id's loop at once
        return time.time() if live() else float("inf")

    def say_wait(msg="", *_a, **_k):
        if "wrong" in str(msg).lower():
            seen["wrong"] = True

    def wait(tok, say=None):
        chat = S.wait_chat_id(tok, say=say_wait, wait_s=_S["wait_s"], sleep=_S["sleep"], clock=clock, code=code)
        seen["chat"] = bool(chat)
        return chat if live() else None

    scratch: dict = {}
    sent = S.setup_telegram(scratch, ask=lambda *_a, **_k: token, say=lambda *_a, **_k: None, wait=wait)
    if not live():
        return {"state": "cancelled", "reason": "cancelled"}
    if not seen["chat"]:
        return {"state": "failed", "reason": "token_refused" if seen["wrong"] else "no_start"}
    if not sent or not isinstance(scratch.get("telegram"), dict):
        return {"state": "failed", "reason": "test_failed", "test_delivered": False}
    try:
        with _LOCK:
            if _W["gen"] != gen:
                return {"state": "cancelled", "reason": "cancelled"}
            raw = S.load_raw()                       # ALERTS_SETUP: load, the telegram entry, save_raw (Discord etc. kept)
            raw["telegram"] = scratch["telegram"]
            S.save_raw(raw)
    except Exception:  # noqa: BLE001
        return {"state": "failed", "reason": "save_failed", "test_delivered": True}
    try:
        if os.path.exists(os.path.join(AB.home(), AB.OFF_NAME)):
            S.switch(True, say=lambda *_a, **_k: None)   # ALERTS_ON.bat exactly: removes the ALERTS_OFF switch file
    except Exception:  # noqa: BLE001
        pass
    return {"state": "done", "reason": None if AB.active() else "bus_off", "test_delivered": True}


def _start_wait(token: str, gen: int, bot_mask: str, code: str | None = None) -> None:
    def run(tok=token):
        try:
            out = _wait_and_save(tok, gen, code)
        except Exception:  # noqa: BLE001   (nothing it raised is printed: an exception text could carry the URL)
            out = {"state": "failed", "reason": "failed"}
        tok = None
        if _set(gen, state=out["state"], reason=out.get("reason"), test_delivered=out.get("test_delivered")):
            log({"t": int(_now()), "action": "wait", "ok": out["state"] == "done", "why": out.get("reason") or "", "bot": bot_mask})
    threading.Thread(target=run, name="alerts_box_wait", daemon=True).start()


def do_connect(body: dict) -> dict:
    """Paste + Connect. -> {"ok", "state", "reason"?, "bot"?, "link"?, "wait_s"?}. Never the token."""
    token = str(body.pop("token", None) or "").strip()
    with _LOCK:
        _W["gen"] += 1                               # a new Connect drops any wait still running
        gen = _W["gen"]
    if not AB.good_token(token):
        _set(gen, state="failed", reason="bad_format", test_delivered=None)
        return {"ok": False, "state": "failed", "reason": "bad_format"}
    user, why = get_me(token)
    if not user:
        _set(gen, state="failed", reason=why, test_delivered=None)
        return {"ok": False, "state": "failed", "reason": why}
    if not _set(gen, state="waiting_start", reason=None, test_delivered=None, t0=_now()):
        return {"ok": False, "state": "cancelled", "reason": "cancelled"}
    import secrets as _sec                           # day-security3: the one-time START code (only this page's link carries it)
    code = _sec.token_urlsafe(9).replace("-", "x").replace("_", "y")
    _start_wait(token, gen, mask_bot(user), code)
    return {"ok": True, "state": "waiting_start", "bot": "@" + user, "link": f"https://t.me/{user}?start={code}", "wait_s": int(_S["wait_s"]),
            "_mask": mask_bot(user)}


def do_cancel() -> dict:
    with _LOCK:
        was = _W["state"] == "waiting_start"
        _W["gen"] += 1
        if was:
            _W.update(state="cancelled", reason="cancelled")
    return {"ok": True, "state": "cancelled" if was else str(_W["state"]), "reason": "cancelled" if was else None}


def do_test() -> dict:
    """TEST_ALERT.bat: one fake entry through every channel; the reply is only {channel: delivered?}."""
    cfg = AB.config()
    res = AB.test_all(cfg)
    chans = {ch: bool(r and r[0]) for ch, r in res.items()}
    good = sum(chans.values())
    return {"ok": good > 0, "channels": chans, "delivered": good, "total": len(chans)}


def status_view() -> dict:
    """Booleans and state words only."""
    try:
        cfg = AB.config()
    except Exception:  # noqa: BLE001
        cfg = {}
    with _LOCK:
        state, reason, test = _W["state"], _W["reason"], _W["test_delivered"]
    return {"ok": True, "state": state or "idle", "reason": reason, "waiting": state == "waiting_start",
            "test_delivered": test, "telegram_set_up": bool(cfg.get("telegram")), "discord_set_up": bool(cfg.get("discord")),
            "bus_on": bool(AB.active(cfg=cfg)), "bus_switched_off": bool(AB.switched_off())}


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="dark">
<title>Phone alerts</title><style>
:root{--bg:#000;--card:#16131e;--line:#3e255e;--edge:#4d2e76;--glow:#9d59ee;--gold:#f1c14b;--mint:#77db89;--fg:#efeaf7;--mut:#a99ebe;--bad:#ff7b7b}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:560px;margin:0 auto;padding:16px 16px calc(28px + env(safe-area-inset-bottom))}
h1{font-size:24px;margin:6px 0 2px;color:var(--gold);letter-spacing:.02em;text-shadow:0 0 14px rgba(241,193,75,.35)}
p.s{color:var(--mut);margin:0 0 14px}
.c{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:14px;box-shadow:0 0 18px rgba(157,89,238,.16)}
.c h2{font-size:17px;margin:0 0 8px;color:var(--gold)}
ol{padding-left:22px;margin:4px 0}li{margin:7px 0}b.k{color:var(--gold)}
code{background:#0b0910;border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:15px;word-break:break-all}
label{display:block;margin:2px 0 6px;color:var(--mut);font-size:14px}
input{width:100%;min-height:48px;font-size:17px;padding:12px;border-radius:10px;border:1px solid var(--edge);background:#0b0910;color:var(--fg)}
input:focus{outline:none;border-color:var(--glow);box-shadow:0 0 0 3px rgba(157,89,238,.35)}
.btn{display:flex;align-items:center;justify-content:center;width:100%;min-height:48px;margin-top:12px;font:inherit;font-size:18px;
font-weight:700;padding:10px 14px;border:0;border-radius:12px;background:var(--gold);color:#1a1300;text-decoration:none;text-align:center;
cursor:pointer;-webkit-tap-highlight-color:transparent}
.btn.sec{background:transparent;color:var(--fg);border:1px solid var(--edge);font-size:16px;font-weight:600;min-height:44px}
.btn.big{min-height:64px;font-size:20px;background:linear-gradient(180deg,#9d59ee,#6a32b5);color:#fff;box-shadow:0 0 24px rgba(157,89,238,.55)}
.btn:disabled{opacity:.5}.row{display:flex;gap:10px}.row .btn{flex:1}
.ok{color:var(--mint)}.bad{color:var(--bad)}.warn{color:var(--gold)}.mut,small{color:var(--mut)}
.big-ok{font-size:21px;font-weight:800;color:var(--mint);text-shadow:0 0 14px rgba(119,219,137,.35)}
a.lnk{color:var(--glow)}[hidden]{display:none!important}
</style></head><body><main>
<h1>Phone alerts</h1><p class="s">Telegram, set up from this phone in 2 minutes. Your trade alerts then come to Telegram first.</p>
<div class="c" id="now"><small>checking the PC…</small></div>
<div class="c" id="s1"><h2>1. Make your bot in Telegram</h2><ol>
<li>Open the <b class="k">Telegram</b> app (not installed? App Store &rarr; Telegram &rarr; sign in with your number).</li>
<li>Search <b class="k">BotFather</b> (blue tick) &rarr; <b>Start</b>.
<a class="btn sec" href="https://t.me/BotFather" rel="noreferrer">Open BotFather</a></li>
<li>Send <code>/newbot</code></li>
<li>Name: <code>Olympus Alerts</code></li>
<li>Username: anything that ends in <code>bot</code>, e.g. <code>olympus_alerts_7731_bot</code></li>
<li>BotFather answers with a long token: <b>long-press it &rarr; Copy</b>. Come back here.</li></ol></div>
<div class="c" id="s2"><h2>2. Paste the token</h2>
<label for="tok">Bot token (hidden; it goes to your PC only)</label>
<input id="tok" type="password" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="paste the token here">
<div id="hint"><small>&nbsp;</small></div>
<div class="row"><button class="btn sec" id="paste" type="button">Paste</button><button class="btn" id="go" type="button">Connect</button></div></div>
<div class="c" id="s3" hidden><h2>3. Tap START in your bot</h2>
<a class="btn big" id="open" href="https://t.me/" rel="noreferrer">Open your bot and tap START</a>
<p id="wait" class="warn">Waiting for your START…</p>
<button class="btn sec" id="cx" type="button">Cancel</button></div>
<div class="c" id="res" hidden></div>
<div class="c"><h2>Check any time</h2><button class="btn sec" id="test" type="button">Send a test alert</button><div id="tout"></div>
<p><small>No sound? iPhone Settings &rarr; Notifications &rarr; Telegram &rarr; Allow + Sounds on.</small></p></div>
<p><small>Private: the PC itself or your own Tailscale phone link only. The token is kept only on the PC
(%USERPROFILE%\.olympus\alerts.json), never in the bot folder or GitHub, never shown again. Messages you send to the bot are ignored.
<a class="lnk" href="/add-account/">Add account</a></small></p>
</main><script>
const $=id=>document.getElementById(id);
const R=__REASONS__;
const RX=/^\d{5,15}:[A-Za-z0-9_-]{30,60}$/;
const CH={telegram:'Telegram',discord:'Discord',ntfy:'ntfy',webpush:'the Olympus app'};
let poll=null,until=0,shown='';
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function ss(k,v){try{if(v===undefined)return sessionStorage.getItem(k);if(v===null)sessionStorage.removeItem(k);else sessionStorage.setItem(k,v)}catch(e){return null}}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Olympus-Alerts':'1'},
body:JSON.stringify(body||{})});let d={};try{d=await r.json()}catch(e){}return d}
function why(code,err){const x=R[code];return x?'<div class="bad"><b>'+esc(x[0])+'</b></div><div>Fix: '+esc(x[1])+'</div>'
:'<div class="bad"><b>'+esc(err||'Not done: nothing changed.')+'</b></div>'}
function res(html){$('res').innerHTML=html;$('res').hidden=false}
function hint(){const v=$('tok').value.trim();$('hint').innerHTML=!v?'<small>&nbsp;</small>':RX.test(v)?
'<small class="ok">Looks like a token ('+v.length+' characters). Tap Connect.</small>':
'<small class="bad">Not a whole token yet: copy all of it (numbers, a colon, then letters).</small>'}
function waiting(on){$('s3').hidden=!on;if(on){$('res').hidden=true;const b=ss('alerts_bot'),l=ss('alerts_link');
if(b&&l){$('open').href=l;$('open').textContent='Open '+b+' and tap START';$('open').hidden=false}else{$('open').hidden=true}
if(!poll)poll=setInterval(load,2000)}else if(poll){clearInterval(poll);poll=null}}
function tick(){if($('s3').hidden)return;const s=Math.max(0,Math.round((until-Date.now())/1000));
$('wait').textContent=until?'Waiting for your START… '+Math.floor(s/60)+':'+String(s%60).padStart(2,'0')+' left':'Waiting for your START…'}
async function load(){let d;try{const r=await fetch('status',{cache:'no-store'});d=await r.json()}catch(e){$('now').innerHTML='<span class="bad">PC not reachable</span>';return}
if(!d.ok){$('now').innerHTML='<span class="bad">'+esc(d.error||'not available')+'</span>';return}
$('now').innerHTML=(d.telegram_set_up?'<span class="ok">Telegram: set up</span>':'<span class="warn">Telegram: not set up yet</span>')
+' · '+(d.bus_on?'<span class="ok">alerts ON</span>':'<span class="mut">alerts on the old path (ntfy + app)</span>')
+(d.telegram_set_up?'<div><small>Connect again only to change the bot.</small></div>':'');
const was=!!poll;waiting(d.state==='waiting_start');
if(d.state===shown)return;shown=d.state;
if(d.state==='done'){ss('alerts_bot',null);ss('alerts_link',null);res('<div class="big-ok">Connected: test delivered</div><div>Telegram just got '
+'"Olympus alerts are ON". Your trade alerts now go there first; ntfy and the Olympus app stay as backups.</div>'
+(d.reason?why(d.reason):''))}
else if(d.state==='failed'||d.state==='cancelled'){res(why(d.reason))}
if(was&&!$('res').hidden)$('res').scrollIntoView({behavior:'smooth',block:'center'})}
async function press(btn,fn){btn.disabled=true;try{await fn()}catch(e){res(why('',"PC not reachable: nothing changed."))}btn.disabled=false}
$('tok').oninput=hint;
$('paste').onclick=async()=>{try{$('tok').value=(await navigator.clipboard.readText()).trim();hint()}
catch(e){$('hint').innerHTML='<small class="warn">Long-press the box above &rarr; Paste.</small>'}};
$('go').onclick=()=>press($('go'),async()=>{const v=$('tok').value.trim();if(!RX.test(v)){res(why('bad_format'));return}
$('res').innerHTML='<small>checking with Telegram…</small>';$('res').hidden=false;
const d=await post('connect',{token:v});$('tok').value='';hint();shown='';
if(d.ok){ss('alerts_bot',d.bot);ss('alerts_link',d.link);until=Date.now()+1000*(d.wait_s||180);waiting(true);tick();shown='waiting_start';$('s3').scrollIntoView({behavior:'smooth',block:'center'})}
else res(why(d.reason,d.error))});
$('cx').onclick=()=>press($('cx'),async()=>{const d=await post('cancel',{});waiting(false);shown='';res(why(d.reason||'cancelled',d.error));load()});
$('test').onclick=()=>press($('test'),async()=>{$('tout').innerHTML='<small>sending…</small>';const d=await post('test',{});
if(!d.channels){$('tout').innerHTML=why('',d.error);return}
$('tout').innerHTML='<div class="'+(d.ok?'ok':'bad')+'">'+d.delivered+' of '+d.total+' delivered</div><div><small>'
+Object.keys(d.channels).map(k=>esc(CH[k]||k)+(d.channels[k]?' &#10003;':' &#10007;')).join(' · ')+'</small></div>'});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});
setInterval(tick,1000);load();
</script></body></html>"""


def page() -> str:
    return PAGE.replace("__REASONS__", json.dumps({k: list(v) for k, v in REASONS.items()}).replace("<", "\\u003c"))


def install(app) -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    nostore = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}

    def _client(request) -> str:
        return getattr(getattr(request, "client", None), "host", None) or ""

    @app.get(PREFIX)
    def r_al_root():
        return RedirectResponse(PREFIX + "/", status_code=307)

    @app.get(PREFIX + "/")
    def r_al_page(request: Request):
        why = link_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        return HTMLResponse(page(), headers={**nostore, "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; "
                                             "style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"})

    @app.get(PREFIX + "/status")
    def r_al_status(request: Request):
        why = link_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        try:
            return JSONResponse(status_view(), headers=nostore)
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"status failed ({e.__class__.__name__})"}, status_code=500, headers=nostore)

    @app.post(PREFIX + "/{action}")
    async def r_al_press(action: str, request: Request):
        raw = b""
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > MAX_BODY:
                break
        code, body = check(action, raw, request.headers, _client(request))
        raw = b""
        if code is not None:
            log({"t": int(_now()), "action": str(action)[:12], "ok": False, "why": str(body.get("error"))[:120]})
            return JSONResponse(body, status_code=code, headers=nostore)
        fn = {"connect": do_connect, "cancel": lambda _b: do_cancel(), "test": lambda _b: do_test()}[action]
        try:
            out = await asyncio.to_thread(fn, body)          # getMe / the test can take seconds: never block the bot server
        except Exception as e:  # noqa: BLE001   (only the class name: an exception text could carry a URL)
            out = {"ok": False, "state": "failed", "reason": "failed", "error": f"it did not run ({e.__class__.__name__})"}
        body.clear()
        bot = out.pop("_mask", "")
        log({"t": int(_now()), "action": action, "ok": bool(out.get("ok")), "why": out.get("reason") or "", "bot": bot,
             **({"delivered": out.get("delivered"), "total": out.get("total")} if action == "test" else {})})
        return JSONResponse(out, status_code=200, headers=nostore)

    _S["installed"] = True
    try:
        from engine import live_site
        live_site.allow_post(allowed)
    except Exception:  # noqa: BLE001
        pass
    return {"page": PREFIX + "/", "actions": list(ACTIONS)}
