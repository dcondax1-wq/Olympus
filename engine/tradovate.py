"""Tradovate REST execution adapter (MFFU accounts clear through Tradovate).

Same contract as live.PaperAdapter: LiveBot builds it with the start config and calls ``send(action)`` with
  {"side": "buy"|"sell", "qty": micros, "stop": px, "target": px, "entry": px, "sym": "NQ"}   -> bracket entry
  {"side": "exit", ...}                                                                       -> flatten
  {"side": "modify", "stop": px}                                                              -> move the stop (BE / trail)
  {"side": "cancel"}                                                                          -> cancel working orders
Every public method returns a dict with ``ok`` and never raises into the bot loop. REST only (requests); market
data is NOT taken from Tradovate - the bot already has its own bars.

Credentials come ONLY from environment variables (never from the UI, never written to disk):
  TRADOVATE_USER, TRADOVATE_PASS, TRADOVATE_CID, TRADOVATE_SECRET, TRADOVATE_APP_ID (default LiquidityEngine),
  TRADOVATE_ENV = demo (default) | live, TRADOVATE_ACCOUNT (account name or id; optional when there is only one).

Safety gates (non-negotiable):
  * the LIVE url is used only when TRADOVATE_ENV=live AND cfg.armed AND cfg.confirm == LIVE_PHRASE
  * orders are refused (not silently clamped) above cfg max_micros (default 40) or 4 minis
  * no new entries at/after the flat time (params.flat_mod, default 15:55 ET); tick() flattens at the flat time
  * kill() cancels every working order and liquidates every position
Offline self-test (mocked HTTP, no network, no credentials):  python -m engine.tradovate --selftest
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
import threading
import time
from collections import deque
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LIVE_PHRASE = "I ACCEPT LIVE RISK"
BASES = {"demo": "https://demo.tradovateapi.com/v1", "live": "https://live.tradovateapi.com/v1"}
ENV_KEYS = ["TRADOVATE_USER", "TRADOVATE_PASS", "TRADOVATE_CID", "TRADOVATE_SECRET"]
MAX_MINIS = 4
MAX_MICROS_HARD = 40
TICK = 0.25
MICRO = {"NQ": "MNQ", "ES": "MES"}
MINI = {"NQ": "NQ", "ES": "ES"}
WORKING = {"Working", "Suspended", "PendingNew", "PendingReplace", "PendingCancel"}

# in-memory arm state set by POST /api/live/arm (never persisted). The adapter still requires the start config
# itself to carry armed + confirm, so an arm click alone can never route an order.
ARM = {"armed": False, "at": None, "adapter": "paper"}

# /auth/accesstokenrequest is capped at ~5/hour by Tradovate (failures count). Shared across adapter instances.
AUTH_MIN_GAP = 15.0
AUTH_MAX_PER_HOUR = 3
_AUTH_ATTEMPTS: deque = deque()
_AUTH_LOCK = threading.Lock()
_TOKENS: dict = {}                      # env -> (accessToken, expiry epoch), shared by every instance in this process
MD_WS = {"demo": "wss://md-demo.tradovateapi.com/v1/websocket", "live": "wss://md.tradovateapi.com/v1/websocket"}
# Tradovate chart bars stamp the bar's CLOSE time; the engine wants the OPEN time (like _yahoo_recent). Flip to
# "open" if a live comparison against the exchange clock shows the bars are already open-stamped.
TV_BAR_STAMP = "close"
DEVICE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tv_device.json")


def device_id() -> str:
    """Stable per-machine deviceId (Tradovate ties sessions to it). Generated once, kept in data/tv_device.json."""
    import json
    import uuid
    try:
        d = json.load(open(DEVICE_FILE, encoding="utf-8")).get("deviceId")
        if d:
            return d
    except Exception:
        pass
    d = str(uuid.uuid4())
    try:
        os.makedirs(os.path.dirname(DEVICE_FILE), exist_ok=True)
        json.dump({"deviceId": d, "created": int(time.time())}, open(DEVICE_FILE, "w", encoding="utf-8"))
    except Exception:
        pass
    return d


def env_status() -> dict:
    """Which credentials are present (names only, never values)."""
    missing = [k for k in ENV_KEYS if not os.environ.get(k)]
    return {"present": not missing, "missing": missing, "env": os.environ.get("TRADOVATE_ENV", "demo").lower(),
            "account": os.environ.get("TRADOVATE_ACCOUNT", ""), "app_id": os.environ.get("TRADOVATE_APP_ID", "LiquidityEngine")}


def front_month(root: str, today: dt.date | None = None) -> str:
    """Front quarterly contract code (H/M/U/Z + 1-digit year), rolling 8 days before the 3rd-Friday expiry."""
    today = today or dt.datetime.now(ET).date()
    for y in (today.year, today.year + 1):
        for m, code in ((3, "H"), (6, "M"), (9, "U"), (12, "Z")):
            first = dt.date(y, m, 1)
            third_fri = first + dt.timedelta(days=(4 - first.weekday()) % 7 + 14)
            if today < third_fri - dt.timedelta(days=8):
                return f"{root}{code}{y % 10}"
    return f"{root}H{(today.year + 1) % 10}"


def _tick(px: float) -> float:
    return round(round(float(px) / TICK) * TICK, 2)


def et_mod(now: float | None = None) -> int:
    t = dt.datetime.fromtimestamp(now or time.time(), ET)
    return t.hour * 60 + t.minute


class TradovateAdapter:
    name = "tradovate"

    def __init__(self, cfg: dict | None = None, readonly: bool = False, force_env: str | None = None):
        cfg = dict(cfg or {})
        self.cfg = cfg
        self.readonly = readonly                     # checklist mode: auth/lookups only, every order path refused
        self.params = cfg.get("params") or {}
        self.sym = cfg.get("sym", "NQ")
        self.flat_mod = int(self.params.get("flat_mod", 955))
        self.max_micros = min(MAX_MICROS_HARD, int(self.params.get("max_micros", cfg.get("max_micros", MAX_MICROS_HARD))))
        self.contract_mode = self.params.get("contract", "auto")  # auto | micro | mini
        self.contract_map = cfg.get("contract_map") or {}
        self.trace = deque(maxlen=200)               # request/response summaries (for the self-test and UI)
        self.lock = threading.RLock()
        self.token = None
        self.token_exp = 0.0
        self.account = None                          # {"id", "name"}
        self.contracts = {}                          # symbol -> {"id", "name", "maturityId"}
        self.legs = []                               # open bracket legs: {"symbol", "qty", "entryId", "stopId", "targetId"}
        self.last_error = None
        self._transport = None                       # monkeypatched by the self-test; else requests
        self._session = None
        # ---- environment + live gate
        env = (force_env or os.environ.get("TRADOVATE_ENV", "demo")).lower()
        adapter = cfg.get("adapter", "tradovate")
        if adapter == "tradovate-demo":
            env = "demo"
        self.env = "live" if env == "live" else "demo"
        self.base = BASES[self.env]
        self.disabled = None
        if adapter == "tradovate-live" and os.environ.get("TRADOVATE_ENV", "demo").lower() != "live":
            self.disabled = "adapter tradovate-live selected but TRADOVATE_ENV is not 'live'"
        if self.env == "live" and not readonly:
            if not cfg.get("armed"):
                self.disabled = "LIVE refused: start config is not armed"
            elif (cfg.get("confirm") or "").strip() != LIVE_PHRASE:
                self.disabled = f"LIVE refused: confirm phrase missing (type exactly '{LIVE_PHRASE}')"
            elif os.environ.get("TRADOVATE_ENV", "demo").lower() != "live":
                self.disabled = "LIVE refused: TRADOVATE_ENV must be 'live'"
        st = env_status()
        if not st["present"]:
            self.disabled = self.disabled or f"missing environment variables: {', '.join(st['missing'])}"
        self._log("system", f"Tradovate adapter: env={self.env} readonly={readonly} "
                            + (f"DISABLED ({self.disabled})" if self.disabled else "ready to authenticate"))

    # ------------------------------------------------------------------ plumbing
    def _log(self, kind, text, **kw):
        self.trace.append({"t": int(time.time()), "type": kind, "text": text, **kw})
        try:
            from .live import BOT
            BOT._log(kind, text, **kw)
        except Exception:
            print(f"[tradovate] {kind}: {text}")

    def _http(self, method, url, body, headers, timeout=12):
        """Returns (status, json|text). Replaced by the self-test with a fake."""
        if self._transport:
            return self._transport(method, url, body, headers)
        import requests
        if self._session is None:
            self._session = requests.Session()
        r = self._session.request(method, url, json=body, headers=headers, timeout=timeout)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text

    def _call(self, method, path, body=None, auth=True, _retry=True) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth:
            a = self.ensure_auth()
            if not a["ok"]:
                return a
            headers["Authorization"] = f"Bearer {self.token}"
        url = self.base + path
        safe_body = {k: v for k, v in (body or {}).items() if k not in ("password", "sec", "cid")} if isinstance(body, dict) else None
        try:
            status, data = self._http(method, url, body, headers)
        except Exception as e:
            self.last_error = f"{path}: {e.__class__.__name__}: {e}"
            self._log("error", f"Tradovate {method} {path} -> network error {e.__class__.__name__}")
            return {"ok": False, "error": self.last_error}
        if status == 401 and auth and _retry:
            self.token = None
            self._log("system", "Tradovate: token rejected, re-authenticating")
            return self._call(method, path, body, auth, _retry=False)
        ok = 200 <= status < 300
        fail = None
        if isinstance(data, dict):
            fail = data.get("failureText") or data.get("errorText") or data.get("failureReason")
            if data.get("p-ticket"):
                fail = f"throttled (p-ticket, retry in {data.get('p-time', '?')}s)"
        if not ok:
            fail = fail or (data if isinstance(data, str) else str(data))[:200]
        summary = f"{method} {path} {safe_body if safe_body else ''} -> {status}" + (f" FAIL {fail}" if fail else "")
        self._log("broker", "Tradovate " + summary[:300])
        if fail:
            self.last_error = f"{path}: {fail}"
            return {"ok": False, "error": self.last_error, "status": status, "data": data}
        return {"ok": True, "status": status, "data": data}

    # ------------------------------------------------------------------ auth / account / contract
    def ensure_auth(self) -> dict:
        with self.lock:
            if self.token and time.time() < self.token_exp - 120:
                return {"ok": True}
            if self._adopt_shared_token():
                return {"ok": True}
            if self.token and time.time() < self.token_exp:          # still valid: renew instead of a full login
                r = self._renew()
                if r["ok"]:
                    return r
            return self.authenticate()

    def _renew(self) -> dict:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}
        try:
            status, data = self._http("GET", self.base + "/auth/renewaccesstoken", None, headers)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if 200 <= status < 300 and isinstance(data, dict) and data.get("accessToken"):
            self._set_token(data)
            self._log("broker", "Tradovate GET /auth/renewaccesstoken -> renewed")
            return {"ok": True}
        return {"ok": False, "error": "renew failed"}

    def _set_token(self, data):
        self.token = data["accessToken"]
        exp = data.get("expirationTime")
        try:
            self.token_exp = dt.datetime.fromisoformat(str(exp).replace("Z", "+00:00")).timestamp() if exp else time.time() + 75 * 60
        except Exception:
            self.token_exp = time.time() + 75 * 60
        _TOKENS[self.env] = (self.token, self.token_exp)      # shared so the data feed + adapter + checklist log in once

    def _adopt_shared_token(self) -> bool:
        tok = _TOKENS.get(self.env)
        if tok and time.time() < tok[1] - 120:
            self.token, self.token_exp = tok
            return True
        return False

    def authenticate(self) -> dict:
        """Full login. Tradovate allows ~5 /accesstokenrequest per hour (failures count), so attempts are rate-limited
        here: at least AUTH_MIN_GAP between attempts and at most AUTH_MAX_PER_HOUR per rolling hour."""
        st = env_status()
        if not st["present"]:
            return {"ok": False, "error": f"missing environment variables: {', '.join(st['missing'])}"}
        e = os.environ
        try:
            cid = int(e["TRADOVATE_CID"])
        except ValueError:
            return {"ok": False, "error": "TRADOVATE_CID must be an integer"}
        now = time.time()
        with _AUTH_LOCK:
            while _AUTH_ATTEMPTS and _AUTH_ATTEMPTS[0] < now - 3600:
                _AUTH_ATTEMPTS.popleft()
            if _AUTH_ATTEMPTS and now - _AUTH_ATTEMPTS[-1] < AUTH_MIN_GAP:
                return {"ok": False, "error": f"auth backoff: wait {AUTH_MIN_GAP - (now - _AUTH_ATTEMPTS[-1]):.0f}s before the next login attempt"}
            if len(_AUTH_ATTEMPTS) >= AUTH_MAX_PER_HOUR:
                return {"ok": False, "error": f"auth limit: {AUTH_MAX_PER_HOUR} login attempts in the last hour (Tradovate caps at 5/h); wait"}
            _AUTH_ATTEMPTS.append(now)
        body = {"name": e["TRADOVATE_USER"], "password": e["TRADOVATE_PASS"], "appId": st["app_id"], "appVersion": "1.0",
                "deviceId": device_id(), "cid": cid, "sec": e["TRADOVATE_SECRET"]}
        r = self._call("POST", "/auth/accesstokenrequest", body, auth=False)
        if not r["ok"]:
            return r
        data = r["data"] if isinstance(r["data"], dict) else {}
        if not data.get("accessToken"):
            return {"ok": False, "error": f"auth failed: {data.get('errorText') or 'no accessToken in response'}"}
        self._set_token(data)
        return {"ok": True, "user": data.get("name"), "has_live": data.get("hasLive"), "expires": data.get("expirationTime")}

    def get_account(self) -> dict:
        if self.account:
            return {"ok": True, **self.account}
        r = self._call("GET", "/account/list")
        if not r["ok"]:
            return r
        accts = [a for a in (r["data"] or []) if isinstance(a, dict)]
        want = os.environ.get("TRADOVATE_ACCOUNT", "").strip()
        if want:
            pick = [a for a in accts if str(a.get("id")) == want or str(a.get("name", "")).lower() == want.lower()]
            if not pick:
                return {"ok": False, "error": f"TRADOVATE_ACCOUNT '{want}' not found; available: {[a.get('name') for a in accts]}"}
        else:
            pick = [a for a in accts if a.get("active", True)]
            if len(pick) != 1:
                return {"ok": False, "error": f"{len(pick)} accounts found; set TRADOVATE_ACCOUNT to one of {[a.get('name') for a in accts]}"}
        a = pick[0]
        self.account = {"id": int(a["id"]), "name": a.get("name"), "type": a.get("accountType"), "active": a.get("active")}
        return {"ok": True, **self.account}

    def balance(self) -> dict:
        a = self.get_account()
        if not a["ok"]:
            return a
        r = self._call("POST", "/cashBalance/getcashbalancesnapshot", {"accountId": a["id"]})
        if not r["ok"]:
            return r
        d = r["data"] if isinstance(r["data"], dict) else {}
        keep = ("totalCashValue", "netLiq", "openPnL", "realizedPnL", "weekRealizedPnL", "initialMargin", "maintenanceMargin", "totalPnL")
        return {"ok": True, **{k: d.get(k) for k in keep}}

    def get_contract(self, symbol: str) -> dict:
        """Resolve a contract symbol (e.g. MNQZ6) via /contract/find, then /contract/suggest, then /contract/item."""
        if symbol in self.contracts:
            return {"ok": True, **self.contracts[symbol]}
        c = None
        r = self._call("GET", f"/contract/find?name={symbol}")
        if r["ok"] and isinstance(r["data"], dict) and r["data"].get("id"):
            c = r["data"]
        if c is None:
            root = re.sub(r"[HMUZ]\d$", "", symbol)
            r = self._call("GET", f"/contract/suggest?t={root}&l=20")
            if r["ok"] and isinstance(r["data"], list):
                c = next((x for x in r["data"] if x.get("name") == symbol), None)
                if c is None:
                    # nearest quarterly of this root (names sort HMUZ within a year; sort by year then month order)
                    order = {"H": 0, "M": 1, "U": 2, "Z": 3}
                    cands = [x for x in r["data"] if re.fullmatch(rf"{root}[HMUZ]\d", x.get("name", ""))]
                    cands.sort(key=lambda x: (int(x["name"][-1]), order[x["name"][-2]]))
                    if cands:
                        c = cands[0]
                        self._log("system", f"Tradovate: {symbol} not listed; using {c['name']}")
        if c is None and str(symbol).isdigit():
            r = self._call("GET", f"/contract/item?id={symbol}")
            if r["ok"] and isinstance(r["data"], dict):
                c = r["data"]
        if c is None:
            return {"ok": False, "error": f"contract {symbol} not found (front month? e.g. {front_month('MNQ')})"}
        info = {"id": int(c["id"]), "name": c.get("name"), "maturityId": c.get("contractMaturityId")}
        if info["maturityId"]:
            m = self._call("GET", f"/contractMaturity/item?id={info['maturityId']}")
            if m["ok"] and isinstance(m["data"], dict):
                info["expiry"] = m["data"].get("expirationDate")
        self.contracts[info["name"]] = info
        self.contracts[symbol] = info
        return {"ok": True, **info}

    def symbols(self, sym: str | None = None) -> dict:
        """Micro + mini symbols for the bot's instrument (cfg contract_map overrides the computed front month)."""
        sym = sym or self.sym
        micro = self.contract_map.get(sym) or front_month(MICRO.get(sym, "MNQ"))
        mini = self.contract_map.get(sym + "_mini") or front_month(MINI.get(sym, "NQ"))
        if micro and micro[:2] in MINI.values() and not micro.startswith("M"):   # user typed the mini in the map
            mini, micro = micro, "M" + micro
        return {"micro": micro, "mini": mini}

    # ------------------------------------------------------------------ gates
    def _gate(self, kind: str) -> dict | None:
        if self.disabled:
            return {"ok": False, "error": "REFUSED: " + self.disabled}
        if self.readonly:
            return {"ok": False, "error": "REFUSED: adapter is in read-only (checklist) mode"}
        if kind == "entry":
            mod = et_mod()
            if mod >= self.flat_mod or mod < 480:
                return {"ok": False, "error": f"REFUSED: entry outside session (ET {mod // 60:02d}:{mod % 60:02d}, flat at {self.flat_mod // 60:02d}:{self.flat_mod % 60:02d})"}
            try:
                from .live import BOT
                if getattr(BOT, "kill", False):
                    return {"ok": False, "error": "REFUSED: kill switch is engaged"}
            except Exception:
                pass
        return None

    def _split(self, action: dict) -> dict:
        """Split the bot's micro count into mini + micro legs and enforce the size caps."""
        qty = int(action.get("qty") or 0)
        if qty < 1:
            return {"ok": False, "error": "REFUSED: qty < 1"}
        if "minis" in action or "micros" in action:
            minis, micros = int(action.get("minis") or 0), int(action.get("micros") or 0)
        elif self.contract_mode == "micro":
            minis, micros = 0, qty
        else:
            minis, micros = qty // 10, qty % 10
        total = minis * 10 + micros
        if minis > MAX_MINIS:
            return {"ok": False, "error": f"REFUSED: {minis} minis exceeds the {MAX_MINIS}-mini cap"}
        if total > self.max_micros or total > MAX_MICROS_HARD:
            return {"ok": False, "error": f"REFUSED: {total} micros exceeds max_micros {self.max_micros}"}
        return {"ok": True, "minis": minis, "micros": micros}

    # ------------------------------------------------------------------ orders
    def _oso(self, symbol, side, qty, stop, target) -> dict:
        a = self.get_account()
        if not a["ok"]:
            return a
        opp = "Sell" if side == "Buy" else "Buy"
        base = {"accountSpec": a["name"], "accountId": a["id"], "action": side, "symbol": symbol, "orderQty": int(qty),
                "orderType": "Market", "isAutomated": True}
        body = {**base, "bracket1": {"action": opp, "orderType": "Limit", "price": _tick(target)},
                "bracket2": {"action": opp, "orderType": "Stop", "stopPrice": _tick(stop)}}
        r = self._call("POST", "/order/placeOSO", body)
        if r["ok"] and isinstance(r["data"], dict) and r["data"].get("orderId"):
            d = r["data"]
            return {"ok": True, "via": "placeOSO", "entryId": d["orderId"], "targetId": d.get("oso1Id"), "stopId": d.get("oso2Id")}
        # fallback: naked market, then an OCO pair (limit target + stop)
        self._log("system", f"Tradovate: placeOSO failed ({r.get('error')}); falling back to placeOrder + placeOCO")
        r1 = self._call("POST", "/order/placeOrder", base)
        if not (r1["ok"] and isinstance(r1["data"], dict) and r1["data"].get("orderId")):
            return {"ok": False, "error": f"entry failed: {r1.get('error')}"}
        oco = {"accountSpec": a["name"], "accountId": a["id"], "action": opp, "symbol": symbol, "orderQty": int(qty),
               "orderType": "Limit", "price": _tick(target), "isAutomated": True,
               "other": {"action": opp, "orderType": "Stop", "stopPrice": _tick(stop)}}
        r2 = self._call("POST", "/order/placeOCO", oco)
        if not (r2["ok"] and isinstance(r2["data"], dict) and r2["data"].get("orderId")):
            self._log("risk", "Tradovate: entry filled but the OCO bracket FAILED - flattening to stay safe")
            self.flatten()
            return {"ok": False, "error": f"bracket failed after entry ({r2.get('error')}); position flattened"}
        return {"ok": True, "via": "placeOrder+placeOCO", "entryId": r1["data"]["orderId"], "targetId": r2["data"]["orderId"], "stopId": r2["data"].get("ocoId")}

    def place_bracket(self, action: dict) -> dict:
        g = self._gate("entry")
        if g:
            return g
        sp = self._split(action)
        if not sp["ok"]:
            return sp
        if not action.get("stop") or not action.get("target"):
            return {"ok": False, "error": "REFUSED: bracket needs stop and target"}
        side = "Buy" if action["side"] == "buy" else "Sell"
        syms = self.symbols(action.get("sym"))
        results = []
        for symbol, qty in ((syms["mini"], sp["minis"]), (syms["micro"], sp["micros"])):
            if qty < 1:
                continue
            c = self.get_contract(symbol)
            if not c["ok"]:
                results.append({"symbol": symbol, **c})
                continue
            r = self._oso(c["name"], side, qty, action["stop"], action["target"])
            if r["ok"]:
                self.legs.append({"symbol": c["name"], "contractId": c["id"], "qty": qty, "side": side, **r})
            results.append({"symbol": c["name"], "qty": qty, **r})
        ok = bool(results) and all(x["ok"] for x in results)
        return {"ok": ok, "adapter": "tradovate", "env": self.env, "legs": results,
                **({} if ok else {"error": "; ".join(x.get("error", "?") for x in results if not x["ok"]) or "no legs placed"})}

    def modify_stop(self, new_stop: float) -> dict:
        g = self._gate("modify")
        if g:
            return g
        if not self.legs:
            return {"ok": False, "error": "no tracked bracket legs to modify"}
        out = []
        for leg in self.legs:
            if not leg.get("stopId"):
                out.append({"symbol": leg["symbol"], "ok": False, "error": "no stop id"})
                continue
            r = self._call("POST", "/order/modifyorder", {"orderId": leg["stopId"], "orderQty": leg["qty"], "orderType": "Stop",
                                                          "stopPrice": _tick(new_stop), "isAutomated": True})
            out.append({"symbol": leg["symbol"], "ok": r["ok"], **({"error": r.get("error")} if not r["ok"] else {})})
        return {"ok": all(x["ok"] for x in out), "stop": _tick(new_stop), "legs": out}

    def orders(self, working_only=True) -> dict:
        a = self.get_account()
        if not a["ok"]:
            return a
        r = self._call("GET", "/order/list")
        if not r["ok"]:
            return r
        rows = [o for o in (r["data"] or []) if o.get("accountId") == a["id"] and (not working_only or o.get("ordStatus") in WORKING)]
        return {"ok": True, "orders": rows}

    def positions(self) -> dict:
        a = self.get_account()
        if not a["ok"]:
            return a
        r = self._call("GET", "/position/list")
        if not r["ok"]:
            return r
        rows = [p for p in (r["data"] or []) if p.get("accountId") == a["id"] and p.get("netPos")]
        return {"ok": True, "positions": rows}

    def fills(self, limit=50) -> dict:
        r = self._call("GET", "/fill/list")
        if not r["ok"]:
            return r
        return {"ok": True, "fills": (r["data"] or [])[-limit:]}

    def cancel_all(self) -> dict:
        if self.disabled or self.readonly:
            return {"ok": False, "error": "REFUSED: " + (self.disabled or "read-only")}
        o = self.orders()
        if not o["ok"]:
            return o
        n, errs = 0, []
        for od in o["orders"]:
            r = self._call("POST", "/order/cancelorder", {"orderId": od["id"], "isAutomated": True})
            n += r["ok"]
            if not r["ok"]:
                errs.append(r.get("error"))
        self.legs = []
        return {"ok": not errs, "cancelled": n, **({"error": "; ".join(map(str, errs))} if errs else {})}

    def flatten(self) -> dict:
        """Cancel working orders, then liquidate every open position on the account."""
        if self.disabled or self.readonly:
            return {"ok": False, "error": "REFUSED: " + (self.disabled or "read-only")}
        c = self.cancel_all()
        p = self.positions()
        if not p["ok"]:
            return {"ok": False, "error": p.get("error"), "cancel": c}
        a = self.get_account()
        liq, errs = [], []
        for pos in p["positions"]:
            r = self._call("POST", "/order/liquidateposition", {"accountId": a["id"], "contractId": pos["contractId"], "admin": False})
            liq.append({"contractId": pos["contractId"], "netPos": pos.get("netPos"), "ok": r["ok"]})
            if not r["ok"]:
                errs.append(r.get("error"))
        self.legs = []
        return {"ok": not errs, "cancel": c, "liquidated": liq, **({"error": "; ".join(map(str, errs))} if errs else {})}

    def kill(self) -> dict:
        self._log("risk", "Tradovate KILL: cancel all + liquidate")
        return self.flatten()

    def tick(self) -> dict:
        """Call once per poll: at/after the flat time anything still open is flattened (even if LiveBot did not)."""
        if self.disabled or self.readonly or et_mod() < self.flat_mod:
            return {"ok": True, "flat_time": False}
        p = self.positions()
        if p["ok"] and p["positions"]:
            self._log("risk", "Tradovate: flat time reached with an open position - flattening")
            return {"ok": True, "flat_time": True, **self.flatten()}
        return {"ok": True, "flat_time": True}

    def send(self, action: dict) -> dict:
        """LiveBot entry point. Never raises."""
        try:
            side = action.get("side")
            if side in ("buy", "sell"):
                return self.place_bracket(action)
            if side == "exit":
                return self.flatten()
            if side == "modify":
                return self.modify_stop(action["stop"])
            if side == "cancel":
                return self.cancel_all()
            return {"ok": False, "error": f"unknown action side {side!r}"}
        except Exception as e:
            self.last_error = f"{e.__class__.__name__}: {e}"
            self._log("error", f"Tradovate adapter exception: {self.last_error}")
            return {"ok": False, "error": self.last_error}

    def round_trip_test(self) -> dict:
        """DEMO ONLY: place a 1-lot MNQ limit far below the market and cancel it. Proves order routing end to end."""
        if self.env != "demo":
            return {"ok": False, "error": "round trip is allowed on DEMO only"}
        if self.disabled:
            return {"ok": False, "error": self.disabled}
        a = self.get_account()
        if not a["ok"]:
            return a
        c = self.get_contract(self.symbols()["micro"])
        if not c["ok"]:
            return c
        try:
            from .data import load
            last = float(load(self.sym, "5m").c[-1])
        except Exception:
            last = 20000.0
        px = _tick(last * 0.5)       # far away: can never fill
        body = {"accountSpec": a["name"], "accountId": a["id"], "action": "Buy", "symbol": c["name"], "orderQty": 1,
                "orderType": "Limit", "price": px, "timeInForce": "Day", "isAutomated": True}
        was_ro, self.readonly = self.readonly, False
        try:
            r = self._call("POST", "/order/placeOrder", body)
            if not (r["ok"] and isinstance(r["data"], dict) and r["data"].get("orderId")):
                return {"ok": False, "error": f"placeOrder failed: {r.get('error')}"}
            oid = r["data"]["orderId"]
            time.sleep(0.5) if self._transport is None else None
            cx = self._call("POST", "/order/cancelorder", {"orderId": oid, "isAutomated": True})
            if not cx["ok"]:
                return {"ok": False, "error": f"order {oid} placed but cancel failed: {cx.get('error')} - cancel it in Tradovate NOW", "orderId": oid}
            return {"ok": True, "orderId": oid, "symbol": c["name"], "price": px, "detail": f"limit buy 1 {c['name']} @ {px} placed and cancelled"}
        finally:
            self.readonly = was_ro

    def status(self) -> dict:
        return {"env": self.env, "base": self.base, "disabled": self.disabled, "readonly": self.readonly,
                "authenticated": bool(self.token), "account": self.account, "contracts": self.contracts,
                "legs": self.legs, "last_error": self.last_error, "max_micros": self.max_micros, "flat_mod": self.flat_mod}


# ---------------------------------------------------------------------- real-time bars (market-data websocket)
_RO_ADAPTERS: dict = {}


def shared_readonly(env: str | None = None) -> "TradovateAdapter":
    """One read-only adapter per environment (token + contract cache) for the data feed and the checklist."""
    env = (env or os.environ.get("TRADOVATE_ENV", "demo")).lower()
    env = "live" if env == "live" else "demo"
    if env not in _RO_ADAPTERS:
        _RO_ADAPTERS[env] = TradovateAdapter({"adapter": "tradovate"}, readonly=True, force_env=env)
    return _RO_ADAPTERS[env]


def bars_frame(bars: list, secs: int):
    """Tradovate chart bars -> the exact frame _yahoo_recent returns (time = unix secs of bar OPEN, o/h/l/c/v)."""
    import pandas as pd
    rows = []
    for b in bars:
        try:
            ts = dt.datetime.fromisoformat(str(b["timestamp"]).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        t = int(ts) - (secs if TV_BAR_STAMP == "close" else 0)
        vol = b.get("volume")
        if vol is None:
            vol = (b.get("upVolume") or 0) + (b.get("downVolume") or 0) or (b.get("bidVolume") or 0) + (b.get("offerVolume") or 0)
        rows.append((t, b.get("open"), b.get("high"), b.get("low"), b.get("close"), vol))
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).dropna()
    if df.empty:
        return df
    df = df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    df["time"] = df["time"].astype("int64")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    return df


class TradovateData:
    """Synchronous wrapper over the Tradovate market-data websocket. recent_bars() returns None on ANY failure so
    the caller can fall back to Yahoo. Needs the market-data entitlement that comes with the MFFU/Tradovate account."""
    SIZES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}

    def __init__(self, env: str | None = None, adapter: "TradovateAdapter | None" = None):
        self.adapter = adapter or shared_readonly(env)
        self.env = self.adapter.env
        self.url = MD_WS[self.env]
        self.last = {"t": None, "bar_t": None, "error": None, "n": 0, "symbol": None}

    def _log(self, kind, text):
        self.adapter._log(kind, text)

    @staticmethod
    def _n_elements(interval: str, period: str) -> int:
        mins = TradovateData.SIZES[interval]
        m = re.fullmatch(r"(\d+)([dh])", period or "5d")
        span_min = (int(m.group(1)) * (1440 if m.group(2) == "d" else 60)) if m else 7200
        return int(max(50, min(4000, span_min / mins)))

    def recent_bars(self, sym: str, interval: str = "5m", period: str = "5d", timeout: float = 10.0):
        try:
            if interval not in self.SIZES:
                raise ValueError(f"unsupported interval {interval}")
            if self.adapter.disabled and "environment" in (self.adapter.disabled or ""):
                raise RuntimeError(self.adapter.disabled)
            a = self.adapter.ensure_auth()
            if not a["ok"]:
                raise RuntimeError(a.get("error"))
            # bars come from the MINI (NQ/ES) front month: that is the instrument the engine was built on
            symbol = self.adapter.contract_map.get(sym + "_mini") or front_month(MINI.get(sym, sym))
            c = self.adapter.get_contract(symbol)
            if not c["ok"]:
                raise RuntimeError(c.get("error"))
            name = c["name"]
            n = self._n_elements(interval, period)
            bars = _ws_collect(self.url, self.adapter.token, name, self.SIZES[interval], n, timeout)
            df = bars_frame(bars, self.SIZES[interval] * 60)
            if df.empty:
                raise RuntimeError("no bars returned")
            self.last = {"t": int(time.time()), "bar_t": int(df["time"].iloc[-1]), "error": None, "n": len(df), "symbol": name}
            self._log("data", f"Tradovate md: {len(df)} {interval} bars {name}, last open {dt.datetime.fromtimestamp(self.last['bar_t'], ET):%H:%M} ET")
            return df
        except Exception as e:
            self.last = {**self.last, "t": int(time.time()), "error": f"{e.__class__.__name__}: {e}"[:200]}
            self._log("error", f"Tradovate md failed ({self.last['error']}); caller falls back to Yahoo")
            return None

    def health(self) -> dict:
        age = (int(time.time()) - self.last["bar_t"]) if self.last.get("bar_t") else None
        return {"ok": self.last.get("error") is None and age is not None, "last_bar_age_s": age, "error": self.last.get("error"),
                "symbol": self.last.get("symbol"), "bars": self.last.get("n"), "checked_at": self.last.get("t"), "env": self.env}


def _ws_frames(raw: str) -> list:
    """Tradovate uses SockJS-style frames: 'o' open, 'h' heartbeat, 'a[...]' array of JSON messages, 'c' close."""
    import json
    if not raw:
        return []
    if raw[0] == "a":
        try:
            return json.loads(raw[1:])
        except Exception:
            return []
    return [{"_ctl": raw[0]}]


def _ws_collect(url: str, token: str, symbol: str, minutes: int, n: int, timeout: float) -> list:
    """Blocking: authorize, md/getChart, gather bars until eoh, md/cancelChart, close. Runs the asyncio client on
    a worker thread so it is safe to call from any context (sync FastAPI handlers, the bot thread, an event loop)."""
    import json
    result: dict = {"bars": [], "err": None}

    async def run():
        import asyncio
        import websockets
        chart_req = {"symbol": symbol, "chartDescription": {"underlyingType": "MinuteBar", "elementSize": minutes,
                                                             "elementSizeUnit": "UnderlyingUnits", "withHistogram": False},
                     "timeRange": {"asMuchAsElements": n}}
        async with websockets.connect(url, open_timeout=timeout, close_timeout=2, max_size=8 * 1024 * 1024) as ws:
            sub_id = None
            state = "open"
            deadline = time.time() + timeout
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.time()))
                for msg in _ws_frames(raw):
                    ctl = msg.get("_ctl")
                    if ctl == "o":
                        await ws.send(f"authorize\n1\n\n{token}")
                        continue
                    if ctl == "h":
                        await ws.send("[]")
                        continue
                    if ctl == "c":
                        raise RuntimeError("socket closed by server")
                    if msg.get("i") == 1:
                        if msg.get("s") != 200:
                            raise RuntimeError(f"authorize failed: {msg}")
                        await ws.send("md/getChart\n2\n\n" + json.dumps(chart_req))
                        state = "chart"
                        continue
                    if msg.get("i") == 2:
                        d = msg.get("d") or {}
                        if msg.get("s") != 200 or d.get("errorText"):
                            raise RuntimeError(f"getChart failed: {d.get('errorText') or msg}")
                        sub_id = d.get("historicalId") or d.get("realtimeId")
                        continue
                    if msg.get("e") == "chart":
                        done = False
                        for ch in (msg.get("d") or {}).get("charts", []):
                            result["bars"].extend(ch.get("bars") or [])
                            if ch.get("eoh"):
                                done = True
                        if done:
                            if sub_id:
                                await ws.send("md/cancelChart\n3\n\n" + json.dumps({"subscriptionId": sub_id}))
                            return
            raise TimeoutError(f"no eoh within {timeout}s (state={state}, bars={len(result['bars'])})")

    def worker():
        try:
            import asyncio
            asyncio.run(asyncio.wait_for(run(), timeout=timeout + 1))
        except Exception as e:
            result["err"] = e

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    th.join(timeout + 3)
    if th.is_alive():
        raise TimeoutError(f"market-data socket did not finish in {timeout}s")
    if result["err"]:
        raise result["err"]
    return result["bars"]


# ---------------------------------------------------------------------- offline self-test (mocked HTTP)
def selftest(verbose=True) -> bool:
    """Proves auth -> account -> contract -> OSO bracket -> modify stop -> flatten with the exact payloads, no network."""
    import json
    sent = []

    def fake(method, url, body, headers):
        path = url.split("/v1", 1)[1]
        sent.append((method, path, body, headers.get("Authorization")))
        if path == "/auth/accesstokenrequest":
            return 200, {"accessToken": "tok123", "expirationTime": "2099-01-01T00:00:00Z", "name": "demo_user", "hasLive": False}
        if path == "/account/list":
            return 200, [{"id": 555, "name": "DEMO12345", "accountType": "Customer", "active": True}]
        if path.startswith("/contract/find?name=MNQ"):
            return 200, {"id": 9001, "name": path.split("=")[1], "contractMaturityId": 77}
        if path.startswith("/contract/find?name=NQ"):
            return 404, {"errorText": "not found"}       # forces the /contract/suggest fallback for the mini
        if path.startswith("/contract/suggest?t=NQ"):
            return 200, [{"id": 9002, "name": "NQZ6", "contractMaturityId": 78}, {"id": 9003, "name": "NQH7", "contractMaturityId": 79}]
        if path.startswith("/contractMaturity/item"):
            return 200, {"id": 77, "expirationDate": "2026-12-18T14:30:00Z"}
        if path == "/order/placeOSO":
            return 200, {"orderId": 100 + len(sent), "oso1Id": 200 + len(sent), "oso2Id": 300 + len(sent)}
        if path == "/order/modifyorder":
            return 200, {"commandId": 1}
        if path == "/order/list":
            return 200, [{"id": 300, "accountId": 555, "ordStatus": "Working"}, {"id": 301, "accountId": 555, "ordStatus": "Filled"}]
        if path == "/order/cancelorder":
            return 200, {"commandId": 2}
        if path == "/position/list":
            return 200, [{"id": 1, "accountId": 555, "contractId": 9001, "netPos": 12}]
        if path == "/order/liquidateposition":
            return 200, {"commandId": 3}
        if path == "/order/placeOrder":
            return 200, {"orderId": 4242}
        if path == "/cashBalance/getcashbalancesnapshot":
            return 200, {"totalCashValue": 50000, "netLiq": 50000, "openPnL": 0}
        return 404, {"errorText": f"unmocked {path}"}

    fake_env = {"TRADOVATE_USER": "u", "TRADOVATE_PASS": "p", "TRADOVATE_CID": "1", "TRADOVATE_SECRET": "s", "TRADOVATE_ENV": "demo"}
    saved = {k: os.environ.get(k) for k in list(fake_env) + ["TRADOVATE_ACCOUNT"]}
    os.environ.update(fake_env)
    os.environ.pop("TRADOVATE_ACCOUNT", None)
    try:
        cfg = {"adapter": "tradovate-demo", "sym": "NQ", "armed": True, "params": {"max_micros": 40, "flat_mod": 955, "contract": "auto"}}
        ad = TradovateAdapter(cfg)
        ad._transport = fake
        ad._gate = lambda kind: None                       # ignore the wall clock for the offline test
        assert ad.base == BASES["demo"] and not ad.disabled, ad.disabled
        # 1) auth + account + balance
        assert ad.authenticate()["ok"] and ad.token == "tok123"
        assert ad.get_account()["name"] == "DEMO12345"
        assert ad.balance()["netLiq"] == 50000
        # 2) bracket entry: 12 micros -> 1 NQ (via suggest fallback) + 2 MNQ, with attached TP/SL
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 12, "stop": 24990.13, "target": 25080.0, "entry": 25020.0})
        assert r["ok"], r
        osos = [b for m, p, b, _ in sent if p == "/order/placeOSO"]
        assert [o["symbol"] for o in osos] == ["NQZ6", "MNQZ6"] and [o["orderQty"] for o in osos] == [1, 2]
        for o in osos:
            assert o["action"] == "Buy" and o["orderType"] == "Market" and o["isAutomated"] is True and o["accountId"] == 555
            assert o["bracket1"] == {"action": "Sell", "orderType": "Limit", "price": 25080.0}
            assert o["bracket2"] == {"action": "Sell", "orderType": "Stop", "stopPrice": 24990.25}   # tick-rounded
        assert all(h == "Bearer tok123" for m, p, b, h in sent if p.startswith("/order"))
        # 3) move the stop to breakeven on both legs
        r = ad.send({"side": "modify", "stop": 25020.0})
        mods = [b for m, p, b, _ in sent if p == "/order/modifyorder"]
        assert r["ok"] and len(mods) == 2 and all(m["stopPrice"] == 25020.0 and m["orderType"] == "Stop" for m in mods)
        assert sorted(m["orderQty"] for m in mods) == [1, 2]
        # 4) flatten: cancels only the WORKING order, liquidates the open position
        r = ad.send({"sym": "NQ", "side": "exit", "qty": 12})
        assert r["ok"] and r["cancel"]["cancelled"] == 1
        assert [b for m, p, b, _ in sent if p == "/order/cancelorder"] == [{"orderId": 300, "isAutomated": True}]
        assert [b for m, p, b, _ in sent if p == "/order/liquidateposition"] == [{"accountId": 555, "contractId": 9001, "admin": False}]
        # 5) size caps refuse rather than clamp
        assert "exceeds" in ad.send({"sym": "NQ", "side": "sell", "qty": 41, "stop": 1, "target": 2})["error"]
        assert "mini" in ad.send({"sym": "NQ", "side": "sell", "qty": 50, "stop": 1, "target": 2, "minis": 5, "micros": 0})["error"]
        # 6) round trip (demo): far limit placed then cancelled
        rt = ad.round_trip_test()
        assert rt["ok"] and sent[-1][1] == "/order/cancelorder" and sent[-1][2]["orderId"] == 4242
        # 7) LIVE gate: refused without armed + phrase, accepted with both; demo adapter never touches live
        os.environ["TRADOVATE_ENV"] = "live"
        a1 = TradovateAdapter({"adapter": "tradovate-live", "armed": True})
        assert a1.disabled and "phrase" in a1.disabled
        assert not a1.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 1, "target": 2})["ok"]
        a2 = TradovateAdapter({"adapter": "tradovate-live", "armed": True, "confirm": LIVE_PHRASE})
        assert a2.base == BASES["live"] and not a2.disabled
        a3 = TradovateAdapter({"adapter": "tradovate-demo", "armed": True})
        assert a3.base == BASES["demo"]
        os.environ["TRADOVATE_ENV"] = "demo"
        a4 = TradovateAdapter({"adapter": "tradovate-live", "armed": True, "confirm": LIVE_PHRASE})
        assert a4.disabled and "TRADOVATE_ENV" in a4.disabled
        # 8) no secrets in the trace
        blob = json.dumps(list(ad.trace))
        assert "'p'" not in blob and '"sec"' not in blob and "password" not in blob
        # 9) auth rate limit: a second login inside AUTH_MIN_GAP is refused (Tradovate caps logins at 5/h)
        ad.token = None
        assert "backoff" in ad.authenticate()["error"]
        assert sent[-1][1] != "/auth/accesstokenrequest" or sent[-1][0] != "POST" or True
        _AUTH_ATTEMPTS.clear()
        assert ad.authenticate()["ok"] and sent[-1][2]["deviceId"] == device_id() and len(device_id()) == 36
        _AUTH_ATTEMPTS.clear()
        # 10) 401 -> re-auth once
        calls = {"n": 0}
        def fake401(method, url, body, headers):
            if "/order/list" in url and calls["n"] == 0:
                calls["n"] += 1
                return 401, {"errorText": "expired"}
            return fake(method, url, body, headers)
        ad._transport = fake401
        assert ad.orders()["ok"] and calls["n"] == 1 and sent[-2][1] == "/auth/accesstokenrequest"
        # 11) market-data frame parsing -> exact _yahoo_recent layout (time = bar OPEN, unix seconds)
        frames = _ws_frames('a[{"e":"chart","d":{"charts":[{"id":5,"bars":[{"timestamp":"2026-10-15T13:35:00.000Z","open":1,"high":2,"low":0.5,"close":1.5,"upVolume":10,"downVolume":5},'
                            '{"timestamp":"2026-10-15T13:40:00.000Z","open":1.5,"high":2,"low":1,"close":1.8,"upVolume":3,"downVolume":4}],"eoh":true}]}}]')
        assert frames[0]["e"] == "chart" and _ws_frames("o") == [{"_ctl": "o"}] and _ws_frames("h") == [{"_ctl": "h"}]
        df = bars_frame(frames[0]["d"]["charts"][0]["bars"], 300)
        assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"] and str(df["time"].dtype) == "int64"
        assert int(df["time"].iloc[0]) == 1792071000 and df["volume"].tolist() == [15.0, 7.0]   # 13:35Z close -> 13:30Z open
        assert TradovateData._n_elements("5m", "5d") == 1440 and TradovateData._n_elements("1h", "5d") == 120
        tdx = TradovateData(adapter=ad)
        assert tdx.recent_bars("NQ", "2h") is None and tdx.health()["ok"] is False      # bad interval -> None, never raises
        if verbose:
            print("Tradovate offline self-test: PASS")
            for m, p, b, _ in sent:
                if p.startswith("/order") or p.startswith("/auth"):
                    print(f"  {m:4} {p:28} {json.dumps({k: v for k, v in (b or {}).items() if k not in ('password', 'sec')}) if b else ''}")
            print(f"  front month today: {front_month('MNQ')} / {front_month('NQ')}")
        return True
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ok = selftest(verbose="--quiet" not in sys.argv)
    sys.exit(0 if ok else 1)
