"""Add account box (owner 2026-11-19: "make an easier way to add this, it should be a typing thing on the dashboard, that's it").

One small page on the PC bot server, on the PC itself (http://localhost:8766/add-account/) or over the owner's PRIVATE Tailscale link
(https://<pc>.<tailnet>.ts.net/add-account/): pick the plan, type (or tap) the NinjaTrader Name, press Add. It runs the SAME code as
ADD_ACCOUNT.bat (engine/account_cli.add: name / size / MFFU slot / one-Rapid checks, CHECK THE NAME warning) and shows [OK] or
NOT ADDED in plain words. It NEVER arms: the account is added DISARMED and joins at the next START BOT, after the owner types
I ACCEPT LIVE RISK himself (Start page on the PC, START_BOT.bat). There is no arm button here on purpose.

  GET  /add-account/         the page
  GET  /add-account/status   the accounts the bot knows (Names masked to the last 4), the MFFU slots, the NinjaTrader Names not added yet
  POST /add-account/add      {"plan": rapideod25 | rapideod | builder25k | builder50k, "name": "<NinjaTrader Name>"}

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
ACTIONS = ("add",)
HEADER = "x-add-account"
MAX_BODY = 2048
RATE_N, RATE_S = 8, 600
PLAN_ORDER = ("rapideod25", "rapideod", "builder25k", "builder50k")
_S: dict = {"installed": False, "log": None}
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
def do_add(body: dict) -> dict:
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
    lines.append("Next: STOP BOT when flat, then START BOT and type I ACCEPT LIVE RISK yourself. Nothing is armed until then.")
    return {"ok": True, "check_name": check_name, "lines": lines}


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
    return {"ok": True, "plans": plans, "accounts": accts, "slots": ac.slots_text(rows), "nt_new": seen}


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
ul{padding-left:18px;margin:6px 0}li{margin:2px 0}small{color:var(--mut)}
</style></head><body><main>
<h1>Add account</h1><p class="s">Adds it DISARMED. Nothing trades until START BOT and you type the live phrase yourself.</p>
<div class="c"><label for="plan">Plan</label><select id="plan"></select>
<label for="name">NinjaTrader Name (Accounts tab)</label><input id="name" autocomplete="off" autocapitalize="off" spellcheck="false"
 placeholder="paste or type the Name">
<div id="seen"></div><button id="go">Add</button><div id="out"></div></div>
<div class="c"><b>The bot knows</b><ul id="acc"><li><small>loading…</small></li></ul><small id="slots"></small></div>
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
}catch(e){$('acc').innerHTML='<li class="bad">PC not reachable</li>'}}
$('go').onclick=async()=>{const name=$('name').value.trim(),plan=$('plan').value;
if(!name){$('out').innerHTML='<div class="bad">Type the Name first.</div>';return}
$('go').disabled=true;$('out').innerHTML='<div><small>checking…</small></div>';
try{const r=await fetch('add',{method:'POST',headers:{'Content-Type':'application/json','X-Add-Account':'1'},body:JSON.stringify({plan,name})});
const d=await r.json();const L=d.lines||[(d.ok?'[OK]':'[NOT ADDED] ')+(d.error||'')];
$('out').innerHTML=L.map(l=>'<div class="'+(/^\\[OK\\]/.test(l)?'ok':/NOT ADDED|refused|private/i.test(l)?'bad':/CHECK THE NAME/.test(l)?'warn':'')+'">'+esc(l)+'</div>').join('');
if(d.ok)$('name').value='';load();}catch(e){$('out').innerHTML='<div class="bad">PC not reachable: nothing changed.</div>'}
$('go').disabled=false};
load();
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
        try:
            out = do_add(body)
        except Exception as e:  # noqa: BLE001
            out = {"ok": False, "lines": [f"[NOT ADDED] it did not run ({e.__class__.__name__}); use ADD_ACCOUNT.bat. Nothing changed."]}
        log({"t": int(_now()), "action": action, "plan": str(body.get("plan"))[:16], "name": mask(body.get("name")),
             "ok": bool(out.get("ok")), "why": "" if out.get("ok") else scrub((out.get("lines") or [""])[0])[:120]})
        return JSONResponse(out, status_code=200, headers=nostore)

    _S["installed"] = True
    try:
        from engine import live_site
        live_site.allow_post(allowed)
    except Exception:  # noqa: BLE001
        pass
    return {"page": PREFIX + "/", "actions": list(ACTIONS)}
