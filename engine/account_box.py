"""Add account box (owner 2026-11-19: "make an easier way to add this, it should be a typing thing on the dashboard, that's it").

One small page on the PC bot server, on the PC itself (http://localhost:8766/add-account/) or over the owner's PRIVATE Tailscale link
(https://<pc>.<tailnet>.ts.net/add-account/): pick the plan, type (or tap) the NinjaTrader Name, press Add. It runs the SAME code as
ADD_ACCOUNT.bat (engine/account_cli.add: name / size / MFFU slot / one-Rapid checks, CHECK THE NAME warning) and shows [OK] or
NOT ADDED in plain words. The account is added DISARMED.

One press to trading (owner 2026-11-20: "if I enter the account name it will start trading automatically"): on the PC itself the
owner may also type I ACCEPT LIVE RISK in the same box. Then, after an [OK] add, the page runs the dashboard's own "Re-arm now"
(engine/onboard.rearm: the phrase checked, STOP only when flat, then the START BOT arm step for EVERY added account, the new one
included). Not flat right now (a trade or a LIT entry waiting) = it waits by itself: every 30 s, at most WAIT_MAX_S, the phrase only
in this server's memory (a restart forgets it), and re-arms the moment the bot is flat. The phrase is never stored, logged or echoed.
Over the owner's private Tailscale link the phrase works too (owner 2026-11-20: "Allow phone arming"): same private_why check as the
Kalshi page (a device signed in to his tailnet; never the home WiFi, Funnel or another tunnel) + same-origin + rate limit.
Claude never arms: only the owner's own typed phrase does.

  GET  /add-account/         the page
  GET  /add-account/status   the accounts the bot knows (Names masked to the last 4), the MFFU slots, the NinjaTrader Names not added yet
  POST /add-account/add      {"plan": rapideod25 | rapideod | builder25k | builder50k | lucidpro50k, "name": "<NinjaTrader Name>", "confirm"?: phrase}
  POST /add-account/start    {"confirm": phrase} start trading every added account now (same Re-arm, waits for flat)
  POST /add-account/cancel   {} drop a waiting start

Every POST must pass check(): not cloud mode; the private link (engine/live_site.private_why: the PC itself, or a device signed in
to the owner's tailnet; never the home WiFi, never Funnel / another tunnel); sent by this page (X-Add-Account: 1 header, JSON,
Sec-Fetch-Site same-origin, Origin = Host, so another web site cannot press it); body <= 2 KB; at most 8 presses in 10 minutes.
Every press is one line in data/account_box.jsonl (plan, ok, short reason, Name masked).
Tests: python -X utf8 -m tests.test_account_box
"""
from __future__ import annotations

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "/add-account"
ACTIONS = ("add", "start", "cancel")
WAIT_MAX_S, WAIT_POLL_S = 8 * 3600, 30.0
HEADER = "x-add-account"
MAX_BODY = 2048
RATE_N, RATE_S = 8, 600
PLAN_ORDER = ("rapideod25", "rapideod", "builder25k", "builder50k", "lucidpro50k")   # lucidpro50k: the second firm (day-nqdash3 2026-11-22), held at START until Lucid's written OK
_S: dict = {"installed": False, "log": None, "rearm": None, "flat": None, "running": None, "sleep": time.sleep}
_W: dict = {"state": None, "t0": None, "said": None, "gen": 0}
_LOCK = threading.Lock()
_HITS: list = []


def _now() -> float:
    return time.time()


def mask(name) -> str:
    s = str(name or "").strip()
    return s if len(s) <= 4 else "…" + s[-4:]


_ID_RX = re.compile(r"[A-Za-z0-9_-]*\d[A-Za-z0-9_-]{7,}")


def scrub(text) -> str:
    """Account-id-like words (8+ letters/digits with a digit) masked to the last 4, for the log."""
    return _ID_RX.sub(lambda m: mask(m.group(0)), str(text or ""))


def log(row: dict) -> None:
    path = _S["log"] or os.path.join(ROOT, "data", "account_box.jsonl")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
    except OSError:
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
        return "cloud mode is paper only: accounts are added on the PC"
    try:
        from engine import live_site
        return live_site.private_why(client, headers)
    except Exception:  # noqa: BLE001
        return "private: the link check could not run"


def origin_why(headers) -> str | None:
    """None = sent by this page (same origin); else why not."""
    h = _h(headers)
    if h.get(HEADER, "").strip() != "1":
        return "not sent by the Add account page (open /add-account/)"
    if "json" not in h.get("content-type", "").lower():
        return "not sent by the Add account page (JSON only)"
    if h.get("sec-fetch-site", "same-origin").strip().lower() not in ("same-origin", "none"):
        return "refused: sent from another site"
    o = h.get("origin", "").strip()
    if not o:
        return "refused: no Origin (open /add-account/)"
    host = h.get("x-forwarded-host") or h.get("host") or ""
    if urllib.parse.urlsplit(o).netloc.lower() != host.strip().lower():
        return "refused: sent from another site"
    return None


def check(action, raw, headers, client, now=None) -> tuple:
    """(None, body) = may run; else (http status, reply)."""
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
    """engine/live_site.guard asks this: the only POST this page may make over the Tailscale link."""
    p = str(path or "")
    return bool(_S["installed"] and (method or "").upper() == "POST" and p.startswith(PREFIX + "/") and p[len(PREFIX) + 1:] in ACTIONS)


# ------------------------------------------------------------------------------------------------ the work (engine/account_cli)
def do_add(body: dict, local: bool = False) -> dict:
    """Exactly ADD_ACCOUNT.bat: engine/account_cli.add(plan, name). Never arms. Reply: {ok, lines: [...]}."""
    from engine import account_cli as ac
    plan = str(body.get("plan") or "").strip().lower()
    name = str(body.get("name") or "").strip().strip('"').strip()
    if plan not in ac.PLANS:
        return {"ok": False, "lines": ["[NOT ADDED] Pick the plan first. Nothing changed."]}
    if not name:
        return {"ok": False, "lines": ["[NOT ADDED] Type the account Name from NinjaTrader (Accounts tab). Nothing changed."]}
    r = ac.add(plan, name)
    if not r.get("ok"):
        return {"ok": False, "lines": [f"[NOT ADDED] {r.get('error')}",
                                       "Nothing changed, the bot keeps trading as before. Fix the Name and press Add again."]}
    lines = [r.get("say") or "[OK]"] + [f"- {n}" for n in (r.get("notes") or [])] + [r.get("slots") or ac.slots_text()]
    check_name = any(str(n).startswith("CHECK THE NAME") for n in (r.get("notes") or []))
    out = {"ok": True, "check_name": check_name, "lines": lines}
    if str(body.get("confirm") or "").strip():
        st = do_start(body, local)
        out["started"] = st.get("ok")
        out["lines"] = lines + st["lines"]
    else:
        lines.append("Next: type I ACCEPT LIVE RISK in the box and press Start trading (or STOP BOT + START BOT). "
                     "Nothing is armed until then.")
    return out


# ------------------------------------------------------------------------------------------------ one press to trading
def _rearm(phrase: str) -> dict:
    if _S["rearm"]:
        return _S["rearm"](phrase)
    from engine import onboard, start_api
    return onboard.rearm(phrase, stop_fn=start_api._stop_fn(), flat_reason=start_api._flat_reason)


def _phrase_ok(raw) -> str | None:
    from engine import go
    p = go.typed_phrase(str(raw or ""))
    return p if p == go.LIVE_PHRASE else None


def do_start(body: dict, local: bool) -> dict:
    """The owner's typed phrase -> Re-arm now (every added account); not flat = wait for flat by itself. Never without the phrase."""
    # local = the PC itself; else check() already proved the owner's own signed-in Tailscale device (never the home WiFi,
    # Funnel or another tunnel). Owner 2026-11-20: "Allow phone arming" - the phrase he types on his phone arms, same as on the PC.
    phrase = _phrase_ok(body.get("confirm"))
    body["confirm"] = None
    if not phrase:
        return {"ok": False, "lines": ["Type I ACCEPT LIVE RISK exactly to start trading. Nothing armed."]}
    r = _rearm(phrase)
    if r.get("ok"):
        _W.update(state="started", t0=_now(), said=r.get("say"), gen=_W["gen"] + 1)
        return {"ok": True, "lines": ["STARTING: " + (r.get("say") or "START runs now with your phrase."),
                                      "Watch it here (Bot line below) or on the Start page; your phone gets the usual alerts."]}
    err = str(r.get("error") or "")
    if err.startswith("Not flat"):
        _wait(phrase)
        return {"ok": True, "waiting": True,
                "lines": [f"WAITING: {err.split(':', 1)[0]}. It starts by itself the moment the bot is flat (checks every "
                          f"{int(WAIT_POLL_S)} s, up to {WAIT_MAX_S // 3600} h). Press Cancel to drop it. Nothing armed yet."]}
    return {"ok": False, "lines": [f"NOT STARTED: {err or 'the START step did not begin'}"]}


def _running() -> bool:
    """The bot runs right now (engine/go.bot_running: the server's own /api/live/state; tests stub _S["running"]). An unknown
    answer is False: the wait below then drops (it never starts a bot it cannot see)."""
    try:
        if _S["running"]:
            return bool(_S["running"]())
        from engine import go
        return bool(go.bot_running())
    except Exception:  # noqa: BLE001
        return False


def _wait(phrase: str) -> None:
    _W.update(state="waiting", t0=_now(), said=None, gen=_W["gen"] + 1)
    gen = _W["gen"]

    def run(p=phrase):
        while _W["gen"] == gen and _now() - _W["t0"] < WAIT_MAX_S:
            _S["sleep"](WAIT_POLL_S)
            if _W["gen"] != gen:
                return
            if not _running():
                # redteam 2026-11-20: it waits for the RUNNING bot to be flat. A bot that is no longer running was stopped
                # (STOP BOT, HOLD TO KILL, a remote stop / kill, a guard) or crashed: re-arming now would start trading again
                # against the owner's own stop (onboard.rearm arms at once when no bot runs). Dropped; one tap starts it again.
                _W.update(state="dropped", said="the bot was stopped while this waited (STOP, kill or a crash): it does not "
                                                "start by itself. Tap Start trading again to start it.")
                log({"t": int(_now()), "action": "start", "ok": False, "why": "dropped: the bot was stopped while it waited"})
                return
            try:
                r = _rearm(p)
            except Exception as e:  # noqa: BLE001
                r = {"ok": False, "error": f"re-arm failed ({e.__class__.__name__})"}
            if r.get("ok"):
                _W.update(state="started", said=r.get("say"))
                log({"t": int(_now()), "action": "start", "ok": True, "why": "waited for flat"})
                return
            if not str(r.get("error") or "").startswith("Not flat"):
                _W.update(state="failed", said=str(r.get("error"))[:200])
                log({"t": int(_now()), "action": "start", "ok": False, "why": scrub(r.get("error"))[:120]})
                return
        if _W["gen"] == gen:
            _W.update(state="gave_up", said=f"still not flat after {WAIT_MAX_S // 3600} h: press Start trading again")
    threading.Thread(target=run, name="account_box_wait", daemon=True).start()


def do_cancel() -> dict:
    was = _W["state"] == "waiting"
    _W.update(state="cancelled" if was else _W["state"], gen=_W["gen"] + 1)
    return {"ok": True, "lines": ["Cancelled: it will not start by itself. Nothing armed." if was else "Nothing was waiting."]}


def bot_line() -> dict:
    w = dict(_W)
    w.pop("gen", None)
    try:
        from engine import go
        j = go.job_status()
        job = {"step": j.get("step"), "state": j.get("state"), "say": j.get("say"), "last": (j.get("lines") or [""])[-1][:160]}
    except Exception:  # noqa: BLE001
        job = None
    return {"wait": w, "job": job}


def status_view() -> dict:
    from engine import account_cli as ac
    rows = ac.inventory()
    added = {r["name"] for r in rows}
    try:
        from engine import go
        bals = go.nt_balances() or {}
    except Exception:  # noqa: BLE001
        bals = {}
    seen = []
    for n, b in sorted(bals.items()):
        if n in added or ac._is_sim(n):
            continue
        try:
            bal = float(b)
        except (TypeError, ValueError):
            bal = None
        seen.append({"name": n, "balance": bal})
    plans = [{"id": k, "label": ac.PLANS[k]["label"], "price": ac.PLANS[k]["price"], "bots": ac.PLANS[k]["bots"]} for k in PLAN_ORDER]
    accts = [{"name": mask(r["name"]), "plan": ac.PLANS.get(r["plan"], {}).get("label", str(r["plan"])), "stage": r["stage"],
              "role": r["role"], "armed": r.get("armed"), "sim": r.get("sim")} for r in rows]
    return {"ok": True, "plans": plans, "accounts": accts, "slots": ac.slots_text(rows), "nt_new": seen, **bot_line()}


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Add account</title><style>
:root{--bg:#0f1115;--card:#181b22;--fg:#e8eaf0;--mut:#9aa3b2;--ok:#3ecf8e;--bad:#ff6b6b;--warn:#f5b942;--acc:#5b8cff;--line:#2a2f3a}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:560px;margin:0 auto;padding:16px}h1{font-size:22px;margin:4px 0 2px}p.s{color:var(--mut);margin:0 0 14px}
.c{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:14px}
label{display:block;font-weight:600;margin:6px 0}select,input{width:100%;box-sizing:border-box;font-size:17px;padding:12px;border-radius:9px;
border:1px solid var(--line);background:#0b0d11;color:var(--fg)}button{width:100%;margin-top:12px;font-size:18px;font-weight:700;padding:13px;
border:0;border-radius:10px;background:var(--acc);color:#fff}button:disabled{opacity:.5}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}.chip{width:auto;margin:0;padding:8px 10px;font-size:14px;background:#26304a}
#out div{margin:3px 0;white-space:pre-wrap}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.row{display:flex;gap:8px}.sec{background:#2b3346;font-size:15px;padding:10px}
ul{padding-left:18px;margin:6px 0}li{margin:2px 0}small{color:var(--mut)}
a.tool{display:flex;align-items:center;justify-content:center;min-height:44px;border:1px solid var(--line);border-radius:10px;color:var(--fg);text-decoration:none;font-weight:600}
</style></head><body><main>
<h1>Add account</h1><p class="s">Type the Name and the phrase: one press adds it AND starts trading (it waits for flat by itself). PC or your Tailscale phone.</p>
<div class="c"><label for="plan">Plan</label><select id="plan"></select>
<label for="name">NinjaTrader Name (Accounts tab)</label><input id="name" autocomplete="off" autocapitalize="off" spellcheck="false"
 placeholder="paste or type the Name">
<div id="seen"></div>
<label for="ph">Start trading now? Type I ACCEPT LIVE RISK (empty = just add)</label><input id="ph" autocomplete="off"
 autocapitalize="characters" spellcheck="false" placeholder="I ACCEPT LIVE RISK">
<button id="go">Add</button><div class="row"><button id="st" class="sec">Start trading (already added)</button>
<button id="cx" class="sec">Cancel waiting</button></div><div id="out"></div></div>
<div class="c"><b>Bot</b><div id="bot"><small>…</small></div></div>
<div class="c"><b>The bot knows</b><ul id="acc"><li><small>loading…</small></li></ul><small id="slots"></small></div>
<p><a class="tool" href="/alerts/">Phone alerts: set up Telegram + test</a></p>
</main><script>
const $=id=>document.getElementById(id);
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function load(){try{const r=await fetch('status',{cache:'no-store'});const d=await r.json();
if(!d.ok){$('acc').innerHTML='<li class="bad">'+esc(d.error||'not available')+'</li>';return}
const keep=$('plan').value;$('plan').innerHTML=d.plans.map(p=>'<option value="'+p.id+'">'+esc(p.label)+' ('+esc(p.bots.toUpperCase())+')</option>').join('');
if(keep)$('plan').value=keep;
$('acc').innerHTML=d.accounts.length?d.accounts.map(a=>'<li>'+esc(a.plan)+' '+esc(a.stage)+' '+esc(a.name)+(a.armed?' · armed':' · not armed')+'</li>').join(''):'<li><small>none yet</small></li>';
$('slots').textContent=d.slots||'';
$('seen').innerHTML=d.nt_new.length?'<small>NinjaTrader shows, not added yet (tap one):</small><div class="chips">'+d.nt_new.map(a=>
'<button class="chip" data-n="'+esc(a.name)+'">'+esc(a.name)+(a.balance!=null?' · $'+Math.round(a.balance).toLocaleString():'')+'</button>').join('')+'</div>':'';
document.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{$('name').value=b.dataset.n});
const w=d.wait||{},j=d.job||{};const W={waiting:'<span class="warn">Waiting for flat, then it starts by itself</span>',started:'<span class="ok">Started: '+esc(w.said||'')+'</span>',
failed:'<span class="bad">Did not start: '+esc(w.said||'')+'</span>',gave_up:'<span class="bad">'+esc(w.said||'')+'</span>',cancelled:'Waiting cancelled'}[w.state]||'';
$('bot').innerHTML=(W?'<div>'+W+'</div>':'')+(j.step?'<div><small>START step: '+esc(j.state||'')+(j.say?' · '+esc(j.say):'')+(j.last?' · '+esc(j.last):'')+'</small></div>':'')||'<small>no start running</small>';
}catch(e){$('acc').innerHTML='<li class="bad">PC not reachable</li>'}}
function show(L){$('out').innerHTML=L.map(l=>'<div class="'+(/^(\\[OK\\]|STARTING)/.test(l)?'ok':/NOT ADDED|NOT STARTED|NOT DONE|refused|private/i.test(l)?'bad':/CHECK THE NAME|WAITING/.test(l)?'warn':'')+'">'+esc(l)+'</div>').join('')}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Add-Account':'1'},body:JSON.stringify(body)});
const d=await r.json();return d.lines?d:{...d,lines:[(d.ok?'[OK] ':'[NOT DONE] ')+(d.error||'')]}}
async function press(btn,fn){btn.disabled=true;$('out').innerHTML='<div><small>working…</small></div>';
try{const d=await fn();show(d.lines);if(d.ok)$('ph').value='';load()}catch(e){show(['[NOT DONE] PC not reachable: nothing changed.'])}btn.disabled=false}
$('go').onclick=()=>{const name=$('name').value.trim(),plan=$('plan').value,confirm=$('ph').value;
if(!name){show(['[NOT ADDED] Type the Name first.']);return}
press($('go'),async()=>{const d=await post('add',{plan,name,confirm});if(d.ok)$('name').value='';return d})};
$('st').onclick=()=>press($('st'),()=>post('start',{confirm:$('ph').value}));
$('cx').onclick=()=>press($('cx'),()=>post('cancel',{}));
$('ph').oninput=()=>{$('go').textContent=$('ph').value.trim()?'Add + start trading':'Add'};
load();setInterval(load,15000);
</script></body></html>"""


def install(app) -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    nostore = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}

    def _client(request) -> str:
        return getattr(getattr(request, "client", None), "host", None) or ""

    @app.get(PREFIX)
    def r_ab_root():
        return RedirectResponse(PREFIX + "/", status_code=307)

    @app.get(PREFIX + "/")
    def r_ab_page(request: Request):
        why = link_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        return HTMLResponse(PAGE, headers={**nostore, "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; "
                                           "style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"})

    @app.get(PREFIX + "/status")
    def r_ab_status(request: Request):
        why = link_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        try:
            return JSONResponse(status_view(), headers=nostore)
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"status failed ({e.__class__.__name__})"}, status_code=500, headers=nostore)

    @app.post(PREFIX + "/{action}")
    async def r_ab_press(action: str, request: Request):
        raw = b""
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > MAX_BODY:
                break
        code, body = check(action, raw, request.headers, _client(request))
        if code is not None:
            log({"t": int(_now()), "action": str(action)[:12], "ok": False, "why": str(body.get("error"))[:120]})
            return JSONResponse(body, status_code=code, headers=nostore)
        from engine import cloud_guard
        local = cloud_guard.local_only(request) is None
        try:
            out = do_add(body, local) if action == "add" else do_start(body, local) if action == "start" else do_cancel()
        except Exception as e:  # noqa: BLE001
            out = {"ok": False, "lines": [f"[NOT DONE] it did not run ({e.__class__.__name__}); use ADD_ACCOUNT.bat / START BOT."]}
        body.pop("confirm", None)
        log({"t": int(_now()), "action": action, "plan": str(body.get("plan"))[:16], "name": mask(body.get("name")),
             "started": out.get("started"), "waiting": out.get("waiting"),
             "ok": bool(out.get("ok")), "why": "" if out.get("ok") else scrub((out.get("lines") or [""])[0])[:120]})
        return JSONResponse(out, status_code=200, headers=nostore)

    _S["installed"] = True
    try:
        from engine import live_site
        live_site.allow_post(allowed)
    except Exception:  # noqa: BLE001
        pass
    return {"page": PREFIX + "/", "actions": list(ACTIONS)}
