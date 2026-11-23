"""KALSHI K8 phone page (owner 2026-11-19: "I have no access to my PC right now, we have to find a way on my phone very quick").

The whole Kalshi set-up and arming from the iPhone, over the PC's PRIVATE Tailscale link only: the bot server's own port
https://<pc>.<tailnet>.ts.net:8444/kalshi-live/ (engine/phone_link.py; :443 belongs to the owner's old Jarvis app). Installed by
engine/phone_safety.install (which
server.py already calls), so server.py is untouched. It never touches the futures bot, NinjaTrader or any futures setting.

  GET  /kalshi-live/         the one-screen page
  GET  /kalshi-live/status   key saved? (never the key), last key check + Kalshi balance, LIVE / PAPER and why, the bet size, the
                             bankroll warning, the legs and times, the caps, the next window, today's and all-time paper / live record
  POST /kalshi-live/key      {"key_id", "private_key"} -> saved OUTSIDE the repo in OLYMPUS_HOME\\kalshi\\ (kalshi_key.pem + key_id.txt,
                             locked to the Windows user), never logged, never echoed; checked at once with ONE signed read (the balance)
  POST /kalshi-live/arm      {"phrase", "stake"} -> the exact phrase (engine/kalshi_live.PHRASE) arms K8 live at the bet size picked
                             ($1 / $2.50 / $5 / $8 / $10 / $15; the bankroll rule says $2.50 for $55); the clock loop is started if
                             it is not running. Nothing else can arm
  POST /kalshi-live/stop     {} -> OFF at once, no second tap: disarm + the kill switch; resting orders cancelled in the background
Every POST must pass check(): the private link (engine/live_site.private_why: the owner's tailnet, signed in, never Funnel), sent by
this page (engine/phone_safety.origin_why: X-Zeus-Safety header, JSON, same Origin, Sec-Fetch-Site), body <= 8 KB, at most 10
presses in 10 minutes. Every press is one line in data/kalshi_live/web_log.jsonl: action, ok, a short reason; never the key, the
key id or the phrase. Public ntfy can never arm anything (nothing here reads it).
Tests: python -X utf8 -m tests.test_kalshi_clock (part w)
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

try:                                    # module level: the route signatures below are resolved by name (postponed annotations)
    from fastapi import Request
except Exception:  # noqa: BLE001
    Request = None

from engine import kalshi_live as KL

PREFIX = "/kalshi-live"
ACTIONS = ("key", "arm", "stop")
MAX_BODY = 8192
RATE_N, RATE_S = 10, 600
_S: dict = {"installed": False, "http": None, "env": None, "state_dir": None, "spawn": None, "clock": None}
_LOCK = threading.Lock()
_HITS: list = []
KEY_ID_RX = re.compile(r"[0-9A-Za-z-]{16,80}")
PEM_RX = re.compile(r"-----BEGIN ([A-Z ]*)PRIVATE KEY-----(.*?)-----END ([A-Z ]*)PRIVATE KEY-----", re.S)


def _now():
    return (_S["clock"] or time.time)()


def _env():
    return _S["env"] if _S["env"] is not None else os.environ


def _P():
    return KL.paths(_S["state_dir"])


def log(row: dict):
    P = _P()
    try:
        os.makedirs(P["dir"], exist_ok=True)
        with open(os.path.join(P["dir"], "web_log.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: row.get(k) for k in ("t", "action", "ok", "why")}) + "\n")
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------------------------------------ the checks (pure)
def _rate_ok(now) -> bool:
    with _LOCK:
        while _HITS and now - _HITS[0] > RATE_S:
            _HITS.pop(0)
        if len(_HITS) >= RATE_N:
            return False
        _HITS.append(now)
        return True


def check(action, raw, headers, client, now=None) -> tuple:
    """(None, body) = may run; else (http status, reply)."""
    from engine import live_site, phone_safety
    now = _now() if now is None else now
    if action not in ACTIONS:
        return 404, {"ok": False, "error": "no such button"}
    why = live_site.private_why(client, headers)
    if why:
        return 403, {"ok": False, "error": why}
    h = {str(k).lower(): str(v) for k, v in (headers.items() if hasattr(headers, "items") else [])}
    if h.get("tailscale-funnel-request"):
        return 403, {"ok": False, "error": "private: never from the internet"}
    why = phone_safety.origin_why(headers)
    if why:
        return 403, {"ok": False, "error": why.replace("ZEUS safety page (open /safety/ on your phone)", "Kalshi page (open /kalshi-live/)")}
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
    """engine/live_site.guard asks this: the only POSTs this page may make over the link."""
    p = str(path or "")
    return bool(_S["installed"] and (method or "").upper() == "POST" and p.startswith(PREFIX + "/") and p[len(PREFIX) + 1:] in ACTIONS)


# ------------------------------------------------------------------------------------------------ the key
def fix_pem(text) -> str | None:
    """The private key as pasted on a phone (spaces or lost line breaks are fine) -> clean PEM, or None."""
    t = str(text or "").replace("\r", "\n").strip()
    m = PEM_RX.search(t)
    if not m:
        return None
    kind, body = m.group(1), re.sub(r"[^A-Za-z0-9+/=]", "", m.group(2))
    if not body or m.group(3) != kind:
        return None
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return f"-----BEGIN {kind}PRIVATE KEY-----\n" + "\n".join(lines) + f"\n-----END {kind}PRIVATE KEY-----\n"


def _lock_down(folder, files):
    try:
        if os.name == "nt":
            import subprocess
            user = os.environ.get("USERNAME") or ""
            if user:
                subprocess.run(["icacls", folder, "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"], capture_output=True, timeout=20)
        else:
            os.chmod(folder, 0o700)
            for f in files:
                os.chmod(f, 0o600)
    except Exception:  # noqa: BLE001
        pass


def save_key(key_id, private_key, env=None) -> tuple:
    """(ok, plain words). Writes OLYMPUS_HOME/kalshi/kalshi_key.pem + key_id.txt (outside the repo), then one signed balance read."""
    env = _env() if env is None else env
    kid = str(key_id or "").strip()
    if not KEY_ID_RX.fullmatch(kid):
        return False, "that is not a Kalshi Key ID (letters, digits and dashes, shown next to the key on kalshi.com)"
    pem = fix_pem(private_key)
    if not pem:
        return False, "that is not a private key: copy the whole text, from -----BEGIN to the end"
    try:
        from cryptography.hazmat.primitives import serialization
        serialization.load_pem_private_key(pem.encode("ascii"), password=None)
    except Exception:  # noqa: BLE001
        return False, "that private key does not load: copy it again (the whole text, nothing cut off)"
    kf = KL.key_files(env)
    folder = kf["dir"]
    if KL.inside_repo(folder):
        return False, "refused: the key folder would be inside the bot folder"
    os.makedirs(folder, exist_ok=True)
    pem_path, id_path = os.path.join(folder, "kalshi_key.pem"), os.path.join(folder, "key_id.txt")
    for path, data in ((pem_path, pem), (id_path, kid)):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="ascii") as fh:
            fh.write(data)
        from engine import fsutil as _fsutil
        _fsutil.replace(tmp, path)
    _lock_down(folder, [pem_path, id_path])
    return check_key(env)


def check_key(env=None) -> tuple:
    env = _env() if env is None else env
    rec = {"t": int(_now()), "ok": False}
    try:
        api = KL.api_from_key(env, http=_S["http"], clock=_S["clock"] or time.time, sleep=lambda s: None)
        b = api.get("/portfolio/balance")
        bal = KL._f(b.get("balance_dollars"), (KL._f(b.get("balance"), 0.0) or 0.0) / 100.0)
        rec.update(ok=True, balance=round(bal, 2))
        said = f"Key OK · balance {KL.money(bal)}"
    except KL.KalshiError as e:
        said = KL.key_fix(e).replace(", then double-click KALSHI_KEY_SETUP.bat again", ", then paste it here again")
        rec["why"] = said[:160]
    KL._jwrite(os.path.join(_P()["dir"], "key_check.json"), rec)
    return rec["ok"], said


def key_status(env=None) -> dict:
    env = _env() if env is None else env
    kf = KL.key_files(env)
    have = bool(kf["key_id"]) and os.path.isfile(kf["key_file"])
    rec = KL._jread(os.path.join(_P()["dir"], "key_check.json"), {}) or {}
    return {"saved": have, "ok": bool(rec.get("ok")) and have, "balance": rec.get("balance"), "checked": rec.get("t"), "why": rec.get("why")}


# ------------------------------------------------------------------------------------------------ the presses
def bankroll_warn(stake, balance) -> str:
    """The bankroll rule (engine/kalshi_clock.bankroll_rule: about 4.5% of the account a bet): a warning when the bet is bigger."""
    from engine import kalshi_clock as KC
    b = KL._f(balance)
    if b is None or KC.fits(stake, b):
        return ""
    r = KC.bankroll_rule(b)
    need = stake / KC.BANKROLL["bet_share"]
    return (f"Bet size {KL.money(stake)} needs about {KL.money(need)} on Kalshi; you have {KL.money(b)}: "
            f"use {KL.money(r['stake_usd'])} a bet ({r['contracts_at_52c']} contracts).")


def do_arm(body) -> dict:
    from engine import kalshi_clock as KC
    stake = KL._f(body.get("stake"))
    if stake not in KC.STAKES:
        return {"ok": False, "said": "pick a bet size: " + ", ".join(KL.money(x) for x in KC.STAKES)}
    ks = key_status()
    if not ks["ok"]:
        return {"ok": False, "said": "save and check your Kalshi key first (step 1)"}
    phrase = re.sub(r"\s+", " ", str(body.get("phrase") or "")).strip()
    if phrase != KL.PHRASE:
        return {"ok": False, "said": f"not armed: type exactly {KL.PHRASE}"}
    P = _P()
    KL._jwrite(KC.stake_path(_S["state_dir"]), {"stake": stake, "t": int(_now()), "by": "phone"})
    ok, msg = KL.arm(phrase, state_dir=_S["state_dir"], env=_env(), now=_now())
    if not ok:
        return {"ok": False, "said": msg}
    try:
        st = KL.load_state(P)
        KL.save_state(P, st)
        KC.maybe_run(say=lambda *_: None, env=_env(), state_dir=_S["state_dir"], spawn_fn=_S["spawn"])
    except Exception:  # noqa: BLE001
        pass
    warn = bankroll_warn(stake, ks.get("balance"))
    return {"ok": True, "said": f"LIVE: K8 at {KL.money(stake)} a bet. The next window places the bets." + (f" {warn}" if warn else "")}


def do_stop() -> dict:
    P = _P()
    now = _now()
    KL.disarm(P, "STOP pressed on the phone page", now)
    try:
        os.makedirs(P["dir"], exist_ok=True)
        with open(P["kill"], "w", encoding="utf-8") as fh:
            fh.write(f"{int(now)} phone page STOP\n")
        KL.command("kill", "phone", _S["state_dir"], now)
    except Exception:  # noqa: BLE001
        pass
    if key_status()["saved"]:
        threading.Thread(target=KL._direct_stop, args=("STOP pressed on the phone page", False, True, _S["state_dir"], _env()),
                         daemon=True).start()
    return {"ok": True, "said": "OFF. No new bets (paper keeps recording). Open bets settle by themselves. To restart: type the phrase."}


def status_view() -> dict:
    from engine import kalshi_clock as KC
    now = _now()
    KC.maybe_run(say=lambda *_: None, env=_env(), state_dir=_S["state_dir"], spawn_fn=_S["spawn"])   # the paper loop runs from the first look
    cfg, probs = KC.load_config(state_dir=_S["state_dir"])
    loop = KC.ClockLoop(state_dir=_S["state_dir"], env=_env(), clock=_S["clock"] or time.time,
                        public_api=KL.Api(http=_S["http"]) if _S["http"] else None)
    s = loop.status()
    ks = key_status()
    P = _P()
    A = KL.load_all(state_dir=_S["state_dir"])
    live, why = KL.arm_state(P=P, sha=A["sha"], env=_env())
    nt = s.get("next")
    bal = KL._f(ks.get("balance"))
    rule = KC.bankroll_rule(bal if bal is not None else cfg.get("bankroll_usd") or 55.0)
    return {"ok": True, "t": int(now), "phrase": KL.PHRASE, "key": ks, "live": live, "why": why, "stake": cfg["stake_usd"],
            "stakes": list(KC.STAKES), "warn": bankroll_warn(cfg["stake_usd"], ks.get("balance")),
            "bankroll": {"balance": bal, "configured": cfg.get("bankroll_usd"), "rule": rule, "fits": KC.fits(cfg["stake_usd"], bal)},
            "dist": KC.kill_distances(_S["state_dir"], cfg, now), "next_t": int(nt) if nt else None, "now_t": int(now),
            "legs": [{"name": KC.LEG[x]["name"], "live": x in cfg["live_legs"]} for x in cfg["paper_legs"]],
            "caps": {"price_cap": cfg["price_cap"], "max_bets_per_day": cfg["max_bets_per_day"], "daily_loss_stop_usd": cfg["daily_loss_stop_usd"],
                     "week_loss_stop_usd": cfg.get("week_loss_stop_usd"),
                     "kill_after_bets": cfg["kill_after_bets"], "kill_min_win_rate": cfg["kill_min_win_rate"],
                     "kill_drawdown_usd": cfg["kill_drawdown_usd"], "kill_avg_price": cfg["kill_avg_price"],
                     "kill_avg_price_bets": cfg["kill_avg_price_bets"]}, "red_team": KC.RED_TEAM,
            "next": KL.et_text(nt) if nt else None, "next_legs": s.get("next_legs"), "paper_today": s["paper_today"],
            "live_today": s["live_today"], "paper_all": s["paper_all"], "live_all": s["live_all"], "last": s["last"],
            "kill": s["kill"], "loop": s["loop"], "paused": s["paused"], "problems": probs}


# ------------------------------------------------------------------------------------------------ the page
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Kalshi K8</title>
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Kalshi K8">
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#111;--mute:#5b6470;--line:#dde1e6;--warn:#b45309;--bad:#b91c1c;--ok:#15803d}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--mute:#9aa4ae;--line:#30363d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.4 -apple-system,system-ui,sans-serif;
padding:16px;padding-top:max(16px,env(safe-area-inset-top))}main{max-width:520px;margin:0 auto}
h1{font-size:22px;margin:4px 0 12px}h2{font-size:17px;margin:0 0 8px}.card{background:var(--card);border:1px solid var(--line);
border-radius:14px;padding:14px;margin:0 0 12px}.row{display:flex;justify-content:space-between;gap:8px;padding:3px 0}
.mute{color:var(--mute);font-size:14px}.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.warnt{color:var(--warn);font-weight:600}input,textarea{width:100%;font:16px/1.3 ui-monospace,Menlo,monospace;padding:10px;border-radius:10px;
border:1px solid var(--line);background:var(--bg);color:var(--ink);margin:4px 0 10px}textarea{height:110px}
button{width:100%;font:600 18px/1 inherit;padding:16px;border-radius:12px;border:2px solid var(--line);background:var(--card);
color:var(--ink);cursor:pointer;margin:2px 0 4px}button.go{border-color:var(--ok);color:var(--ok)}
button.stop{background:var(--bad);border-color:var(--bad);color:#fff;font-size:22px;padding:22px}
.sizes{display:flex;gap:8px}.sizes label{flex:1;text-align:center;border:2px solid var(--line);border-radius:10px;padding:12px 0;font-weight:600}
.sizes input{display:none}.sizes input:checked+span{color:var(--ok)}.phr{font:700 17px ui-monospace,Menlo,monospace;letter-spacing:.02em}
#said{font-weight:600}ul{margin:4px 0 0;padding-left:18px}li{margin:2px 0;font-size:14px}
.big{font-size:28px;font-weight:700;letter-spacing:-.01em}.chips{display:flex;gap:4px;flex-wrap:wrap;margin:4px 0 2px}
.chip{width:22px;height:22px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;font:700 12px/1 system-ui;color:#fff}
.chip.w{background:var(--ok)}.chip.l{background:var(--bad)}.bar{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin:2px 0 8px}
.bar i{display:block;height:100%;background:var(--ok)}.bar i.hot{background:var(--warn)}.bar i.red{background:var(--bad)}
.kv{display:grid;grid-template-columns:1fr auto;gap:2px 10px;font-size:15px}.kv b{text-align:right}
.sizes label.rec{border-color:var(--ok)}.sizes small{display:block;font-weight:400;font-size:11px;color:var(--mute)}
</style></head><body><main>
<h1>Kalshi K8</h1>
<button id="b-stop" class="stop">STOP (off now)</button>
<div class="card" id="st"><h2>K8 status</h2><div class="mute">Loading...</div></div>
<div class="card" id="said" hidden></div>
<div class="card"><h2>1. Your Kalshi key</h2><div id="keyst" class="mute"></div>
<input id="kid" placeholder="Key ID (from kalshi.com, API Keys)" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false">
<textarea id="pk" placeholder="Paste the private key here (-----BEGIN ... PRIVATE KEY----- to the end)" autocomplete="off" autocapitalize="off"
 autocorrect="off" spellcheck="false"></textarea>
<button id="b-key">Save + check the key</button>
<p class="mute">Saved only on your PC, outside the bot folder. Never shown again, never sent anywhere but Kalshi.</p></div>
<div class="card"><h2>2. The strategy (K8 clock bets)</h2><div id="strat" class="mute"></div><p class="warnt" id="redteam"></p></div>
<div class="card"><h2>3. Bet size, then the phrase</h2>
<div class="sizes" id="sizes"></div><div id="warn" class="warnt"></div>
<p>Type exactly: <span class="phr" id="phr"></span></p>
<input id="phrase" placeholder="type the phrase" autocomplete="off" autocapitalize="characters" autocorrect="off" spellcheck="false">
<button id="b-arm" class="go">Start LIVE</button>
<p class="mute">Only this typed phrase starts real money. STOP turns it off at once. It never touches the futures bot.</p></div>
<div class="card"><h2>Last bets</h2><ul id="last"><li class="mute">none yet</li></ul></div>
</main><script>
var S=null,STAKE=null,NEXT=null,SKEW=0;
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function usd(x,sg){var v=Number(x||0);return (v<0?"-":(sg&&v>0?"+":""))+"$"+Math.abs(v).toFixed(2)}
function rec(s){return s&&s.n?(s.n+" bets, "+s.won+" won, "+usd(s.net,1)):"no bets yet"}
function say(t,bad){var e=document.getElementById("said");e.hidden=!t;e.textContent=t||"";e.className="card "+(bad?"bad":"ok")}
function load(){fetch("status",{cache:"no-store"}).then(function(r){return r.json()}).then(function(s){S=s;if(!s.ok){document.getElementById("st").innerHTML='<div class="bad">'+esc(s.error||"not available")+'</div>';return}
 var d=s.dist||{},bk=s.bankroll||{},r=(bk.rule||{}),led=d.ledger==="live"?"live":"paper",td=led==="live"?s.live_today:s.paper_today;
 var h='<h2>K8 status</h2><div class="row"><span class="big '+(s.live?"ok":"warnt")+'">'+(s.live?"LIVE":"PAPER")+'</span><span class="mute" style="text-align:right">'+(s.live?"real bets, "+esc(usd(s.stake))+" each":"no real money: "+esc(s.why))+'</span></div>';
 h+='<div class="kv"><span>Bankroll</span><b>'+(bk.balance!=null?esc(usd(bk.balance))+" on Kalshi":esc(usd(bk.configured))+" (planned)")+'</b>';
 h+='<span>Bet size</span><b>'+esc(usd(s.stake))+(bk.fits===false?' <span class="bad">too big</span>':'')+'</b>';
 h+='<span>Today ('+led+')</span><b>'+esc(rec(td))+'</b>';
 h+='<span>Next window</span><b id="cd">'+esc(s.next||"-")+'</b><span></span><b class="mute" style="font-weight:400">'+esc((s.next_legs||[]).join(", "))+'</b></div>';
 var l10=d.last10||[];h+='<div class="mute" style="margin-top:8px">Last '+l10.length+' results ('+led+'), oldest first</div><div class="chips">'+(l10.length?l10.map(function(x){return '<span class="chip '+(x.result==="won"?"w":"l")+'" title="'+esc(x.day+" "+x.name+" "+usd(x.pnl,1))+'">'+(x.result==="won"?"W":"L")+'</span>'}).join(""):'<span class="mute">none yet</span>')+'</div>';
 function bar(lbl,used,stop){var f=stop?Math.min(1,Math.max(0,used/stop)):0;return '<div class="row"><span>'+lbl+'</span><b>'+esc(usd(-used))+' of '+esc(usd(-stop))+'</b></div><div class="bar"><i class="'+(f>.8?"red":f>.5?"hot":"")+'" style="width:'+Math.round(100*f)+'%"></i></div>'}
 h+='<div class="mute" style="margin-top:6px">How far each stop is</div>'+bar("Today",(d.day||{}).used||0,(d.day||{}).stop||0)+bar("This week",(d.week||{}).used||0,(d.week||{}).stop||0)+bar("From the peak (OFF)",(d.drawdown||{}).used||0,(d.drawdown||{}).stop||0);
 var wr=d.win_rate||{},ap=d.avg_price||{};h+='<div class="kv"><span>Won</span><b>'+(wr.n?Math.round(100*wr.rate)+'% of '+wr.n+' (OFF under '+Math.round(100*(wr.min||0))+'% after '+wr.of+')':'no bets yet')+'</b><span>Average price</span><b>'+(ap.avg!=null?Math.round(100*ap.avg)+'c (OFF over '+Math.round(100*(ap.max||0))+'c on '+ap.of+')':'-')+'</b></div>';
 h+='<div class="mute" style="margin-top:6px">'+esc(s.kill)+(s.loop?"":" &middot; the clock loop is not running yet")+(s.paused?" &middot; PAUSED":"")+'</div>';
 NEXT=s.next_t;SKEW=(s.now_t||0)*1000-Date.now();
 document.getElementById("st").innerHTML=h;
 var k=s.key||{};document.getElementById("keyst").innerHTML=k.ok?'<span class="ok">Key OK &middot; balance '+esc(usd(k.balance))+'</span>':(k.saved?'<span class="bad">'+esc(k.why||"saved, not checked yet")+'</span>':'No key saved yet.');
 var c=s.caps||{};document.getElementById("strat").innerHTML='<ul>'+(s.legs||[]).map(function(l){return "<li>"+esc(l.name)+(l.live?"":" (paper only)")+"</li>"}).join("")+'</ul>'
  +'<p>'+esc(usd(s.stake))+' a bet at the best ask, 20 s after the window opens; skipped above '+Math.round((c.price_cap||0)*100)+'c. At most '+esc(c.max_bets_per_day)+' bets a day, stop at '+esc(usd(-(c.daily_loss_stop_usd||0)))+' a day and '+esc(usd(-(c.week_loss_stop_usd||0)))+' a week, OFF under '+Math.round((c.kill_min_win_rate||0)*100)+'% won after '+esc(c.kill_after_bets)+' bets, at '+esc(usd(-(c.kill_drawdown_usd||0)))+' from the peak, or above '+Math.round((c.kill_avg_price||0)*100)+'c paid on average over the last '+esc(c.kill_avg_price_bets)+' bets.</p>';
 document.getElementById("redteam").textContent=s.red_team||"";
 if(STAKE===null)STAKE=s.stake;var rs=((s.bankroll||{}).rule||{}).stake_usd;document.getElementById("sizes").innerHTML=(s.stakes||[]).filter(function(v){return v<=Math.max(5,rs||0)}).map(function(v){return '<label'+(v==rs?' class="rec"':'')+'><input type="radio" name="sz" value="'+v+'"'+(v==STAKE?" checked":"")+'><span>$'+v+(v==rs?'<small>the rule</small>':'')+'</span></label>'}).join("");
 [].forEach.call(document.querySelectorAll('#sizes input'),function(i){i.onchange=function(){STAKE=Number(i.value);warn()}});
 document.getElementById("phr").textContent=s.phrase;warn();
 document.getElementById("last").innerHTML=(s.last||[]).slice().reverse().map(function(r){return "<li>"+esc(r.day)+" &middot; "+esc(r.leg)+" &middot; "+esc(r.status)+(r.result?" &middot; "+esc(r.result)+" "+esc(usd(r.pnl,1)):"")+"</li>"}).join("")||'<li class="mute">none yet</li>';
}).catch(function(){document.getElementById("st").innerHTML='<div class="bad">The PC does not answer. Use STOP again later or the Kalshi app.</div>'})}
function warn(){var k=(S&&S.key)||{},b=Number(k.balance),fit=Math.min(15,Math.max(1,Math.round(b*0.045/0.5)*0.5)),w="";if(k.ok&&isFinite(b)&&STAKE>fit+1e-9)w="Bet size $"+STAKE+" needs about $"+(STAKE/0.045).toFixed(0)+" on Kalshi; you have "+usd(b)+": use $"+fit+" a bet.";document.getElementById("warn").textContent=w}
function tick(){var e=document.getElementById("cd");if(!e||!NEXT)return;var x=Math.round((NEXT*1000-(Date.now()+SKEW))/1000);if(x<=0){e.textContent="now";return}var h=Math.floor(x/3600),m=Math.floor(x%3600/60),q=x%60;e.textContent=(h?h+"h ":"")+(h||m?m+"m ":"")+(h?"":q+"s")+" ("+S.next+")"}
function post(a,body,btn){btn.disabled=true;say("Sending...");fetch(a,{method:"POST",headers:{"Content-Type":"application/json","X-Zeus-Safety":"1"},body:JSON.stringify(body)})
 .then(function(r){return r.json()}).then(function(j){say(j.said||j.error||"",!j.ok);load()}).catch(function(){say("NOT SENT: the PC does not answer.",1)}).then(function(){btn.disabled=false})}
document.getElementById("b-key").onclick=function(){var kid=document.getElementById("kid"),pk=document.getElementById("pk");post("key",{key_id:kid.value,private_key:pk.value},this);pk.value=""};
document.getElementById("b-arm").onclick=function(){var p=document.getElementById("phrase");post("arm",{phrase:p.value,stake:STAKE},this);p.value=""};
document.getElementById("b-stop").onclick=function(){post("stop",{},this)};
load();setInterval(load,15000);setInterval(tick,1000);
</script></body></html>"""


# ------------------------------------------------------------------------------------------------ wiring
def install(app) -> dict:
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from engine import live_site
    nostore = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}

    def _client(request) -> str:
        return getattr(getattr(request, "client", None), "host", None) or ""

    @app.get(PREFIX)
    def r_kl_root():
        return RedirectResponse(PREFIX + "/", status_code=307)

    @app.get(PREFIX + "/")
    def r_kl_page(request: Request):
        why = live_site.private_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        return HTMLResponse(PAGE, headers={**nostore, "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; "
                                           "style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"})

    @app.get(PREFIX + "/status")
    def r_kl_status(request: Request):
        why = live_site.private_why(_client(request), request.headers)
        if why:
            return JSONResponse({"ok": False, "error": why}, status_code=403, headers=nostore)
        try:
            return JSONResponse(status_view(), headers=nostore)
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": f"status failed ({e.__class__.__name__})"}, status_code=500, headers=nostore)

    @app.post(PREFIX + "/{action}")
    async def r_kl_press(action: str, request: Request):
        raw = b""
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > MAX_BODY:
                break
        code, body = check(action, raw, request.headers, _client(request))
        raw = b""                                           # the key text lives no longer than this request
        if code is not None:
            log({"t": int(_now()), "action": str(action)[:12], "ok": False, "why": str(body.get("error"))[:120]})
            return JSONResponse(body, status_code=code, headers=nostore)
        try:
            if action == "key":
                ok, said = save_key(body.get("key_id"), body.get("private_key"))
                out = {"ok": ok, "said": said}
            elif action == "arm":
                out = do_arm(body)
            else:
                out = do_stop()
        except Exception as e:  # noqa: BLE001  (never the body in an error)
            out = {"ok": False, "said": f"it did not work ({e.__class__.__name__}); try again or use STOP"}
        body = None
        log({"t": int(_now()), "action": action, "ok": bool(out.get("ok")), "why": "" if out.get("ok") else str(out.get("said"))[:120]})
        return JSONResponse(out, status_code=200, headers=nostore)

    _S["installed"] = True
    try:
        live_site.allow_post(allowed)
    except Exception:  # noqa: BLE001
        pass
    return {"page": PREFIX + "/", "actions": list(ACTIONS)}
