"""Kalshi LIVE executor (engine/kalshi_live.py): every safety rule on a FAKE Kalshi (no network, no real key, no real order).

  a. signing    RSA-PSS and Ed25519 requests verify on the fake (timestamp ms + METHOD + /trade-api/v2/path, no query); only the
                allow-listed calls exist (no transfer / key / v1 order endpoint); Kalshi hosts only; no signed call without a key;
                errors never show the key id, the key path or a signature; a key inside the bot folder is refused
  b. plan       the fixture plan validates; caps above the hard ceilings, a bad status, a missing stop = problems (cannot arm);
                an unknown pause rule skips that market; candidates: proposal runnable, PAPER ONLY skipped; one hash over both
  c. caps       check_order: EACH cap blocks an order (kill, not armed, stopped, paused, not post-only, expiry, price, size, market
                closed, stale book, cross, per-market, capital, cash, open orders, day stop, stop room, rate, day orders, taker
                band, flatten not held, a broken view) and a good order passes
  d. arming     OFF by default; the futures phrase / a wrong phrase / LE_KALSHI_LIVE=0 refused; the exact phrase arms (the phrase
                is never stored); a plan change / a new executor version / a forged record = OFF; KALSHI_LIVE.bat (--go): plan, limits,
                key check, dry run, then only the typed phrase arms + starts the loop; a plan changed under his eyes is refused
  e. loop       quotes (post-only, GTC, expiring <= 20 min, olyk- ids, V2 body), kept when nothing moved, re-quoted when the book
                moves, renewed before expiry; fills + settlement -> day P&L = the fake's own (real-model) accounting; a restart
                adopts our resting orders (no duplicates); a foreign order counts in the caps but is never touched by a re-quote
  f. stops      daily loss stop, kill switch, phone pause / resume / flatten / kill, plan change, 3 rejects, 410, 401, positions
                mismatch, Kalshi silent 15 min, LE_KALSHI_LIVE=0: each cancels, switches OFF (re-arm needs the phrase), pushes once
  g. alerts     a busy 30 h: <= 10 non-stop pushes per ET day (fills batched <= 6, one day summary), a stop always goes out;
                no key id in any push; ASCII titles
  h. dry run    public prices only: what it would place, zero writes, no key, no state; .bat / .ps1 static checks
  i. card+phone the <= 200-byte card (idle when no loop runs); phone presses do nothing while OFF; a ZEUS Safety press reaches Kalshi
                when ON; maybe_run; KALSHI_STOP.bat (--stop) cancels everything itself when no loop runs, says 'OFF already' when never on
  j. wiring     run_area kalshi lists this suite; .gitignore; the Kalshi page says "PAUSED: ready to go live when you type the phrase"

  python -X utf8 -m tests.test_kalshi_live
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import math
import os
import re
import shutil
import sys
import tempfile
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa  # noqa: E402

from engine import kalshi_live as KL  # noqa: E402

KL.CLOCK_PATH = os.path.join(ROOT, "tests", "fixtures", "kalshi_live", "clock_off.json")   # this suite: the maker / taker executor only
RES: list = []
FIX = os.path.join(ROOT, "tests", "fixtures", "kalshi_live")
PLAN = os.path.join(FIX, "plan.json")
CANDS = os.path.join(FIX, "candidates")
T0 = dt.datetime(2026, 11, 18, 15, 0, tzinfo=dt.timezone.utc).timestamp()      # Wed 10:00 AM ET
KEY_ID = "a952bcbe-ec3b-4b5b-b8f9-11dae589608c"
ALERT = {"ntfy": "https://ntfy.example", "topic": "test-topic"}


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:600]}"), flush=True)
    return bool(cond)


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat().replace("+00:00", "Z")


class Clock:
    def __init__(self, t=T0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def add(self, s):
        self.t += s
        return self.t


# ================================================================================================ the fake Kalshi
class FakeKalshi:
    """Kalshi trade API v2 as docs.kalshi.com describes it (2026-11), in memory. Real-model accounting: long YES / long NO with
    netting, cash moves like Kalshi's (buying NO costs 1 - p), so the executor's signed-model P&L is checked against it."""
    ROOT = "https://api.elections.kalshi.com"

    def __init__(self, clock, pub, key_id=KEY_ID, cash=100.0):
        self.clock, self.pub, self.key_id = clock, pub, key_id
        self.cash, self.pos, self.cost = cash, {}, {}
        self.orders, self.fills, self.settles = {}, [], []
        self.markets, self.books, self.programs, self.series_markets = {}, {}, [], {}
        self.trading, self.down, self.fail = True, False, {}
        self.calls, self.n, self.maker_rate = [], 0, 0.0175
        self.sig_fail = 0

    # ---------------------------------------------------------------- helpers the tests use
    def market(self, t, yes, no, close_h=48, status="active"):
        self.markets[t] = {"ticker": t, "event_ticker": t.rsplit("-", 1)[0], "status": status, "close_time": iso(self.clock() + close_h * 3600),
                           "result": "", "yes_sub_title": f"Fake market {t}", "price_ranges": [{"start": "0.0000", "end": "1.0000", "step": "0.0100"}]}
        self.books[t] = (list(yes), list(no))

    def program(self, t, usd_day, target=1000.0, days=7):
        a = self.clock() - 86400
        self.programs.append({"market_ticker": t, "series_ticker": t.split("-")[0], "incentive_type": "liquidity", "start_date": iso(a),
                              "end_date": iso(a + days * 86400), "period_reward": int(usd_day * days * 1e4), "target_size_fp": f"{target:.2f}",
                              "discount_factor_bps": 5000, "incentive_description": "fake"})

    def mid(self, t):
        yes, no = self.books[t]
        bid = max(p for p, _ in yes) if yes else None
        ask = 1 - max(p for p, _ in no) if no else None
        return (bid + ask) / 2

    def value(self):
        v = 0.0
        for t, p in self.pos.items():
            m = 1.0 if self.markets[t]["result"] == "yes" else 0.0 if self.markets[t]["result"] == "no" else self.mid(t)
            v += p * m if p > 0 else -p * (1 - m)
        return v

    def equity(self):
        return self.cash + self.value()

    def ours(self):
        return [o for o in self.orders.values() if o["client_order_id"].startswith("olyk-")]

    def posts(self, since=0):
        return [c for c in self.calls[since:] if c[0] == "POST"]

    def deletes(self, since=0):
        return [c for c in self.calls[since:] if c[0] == "DELETE"]

    def apply_fill(self, oid, t, side, n, p, taker):
        rate = 0.07 if taker else self.maker_rate
        fee = math.ceil(rate * n * p * (1 - p) * 100 - 1e-9) / 100.0
        pos, cost = self.pos.get(t, 0.0), self.cost.get(t, 0.0)
        if side == "bid":
            k = min(n, max(-pos, 0.0))
            if k:
                cost -= cost * k / abs(pos)
                self.cash += k * (1 - p)
                pos += k
            r = n - k
            if r:
                self.cash -= r * p
                cost += r * p
                pos += r
        else:
            k = min(n, max(pos, 0.0))
            if k:
                cost -= cost * k / pos
                self.cash += k * p
                pos -= k
            r = n - k
            if r:
                self.cash -= r * (1 - p)
                cost += r * (1 - p)
                pos -= r
        self.cash -= fee
        self.pos[t], self.cost[t] = pos, max(cost, 0.0)
        if abs(pos) < 1e-9:
            self.pos.pop(t, None)
            self.cost.pop(t, None)
        self.n += 1
        self.fills.append({"fill_id": f"fill{self.n}", "trade_id": f"fill{self.n}", "order_id": oid, "ticker": t, "market_ticker": t,
                           "book_side": side, "outcome_side": "yes" if side == "bid" else "no", "count_fp": f"{n:.2f}",
                           "yes_price_dollars": f"{p:.4f}", "no_price_dollars": f"{1 - p:.4f}", "is_taker": taker, "fee_cost": f"{fee:.4f}",
                           "created_time": iso(self.clock()), "ts": int(self.clock())})

    def fill(self, oid, n=None):
        o = self.orders[oid]
        n = o["rem"] if n is None else n
        self.apply_fill(oid, o["ticker"], o["book_side"], n, o["p"], False)
        o["rem"] -= n
        if o["rem"] <= 1e-9:
            self.orders.pop(oid)

    def settle(self, t, result):
        pos = self.pos.pop(t, 0.0)
        cost = self.cost.pop(t, 0.0)
        yes_n, no_n = max(pos, 0.0), max(-pos, 0.0)
        pay = yes_n * (result == "yes") + no_n * (result == "no")
        self.cash += pay
        self.markets[t].update(status="finalized", result=result)
        for oid in [i for i, o in self.orders.items() if o["ticker"] == t]:
            self.orders.pop(oid)
        self.settles.append({"ticker": t, "event_ticker": t.rsplit("-", 1)[0], "exchange_index": 0, "market_result": result,
                             "yes_count_fp": f"{yes_n:.2f}", "yes_total_cost_dollars": f"{cost if pos > 0 else 0:.4f}",
                             "no_count_fp": f"{no_n:.2f}", "no_total_cost_dollars": f"{cost if pos < 0 else 0:.4f}",
                             "revenue": int(round(pay * 100)), "settled_time": iso(self.clock()), "fee_cost": "0.0000"})

    def foreign(self, t, side, p, n):
        self.n += 1
        oid = f"foreign{self.n}"
        self.orders[oid] = {"order_id": oid, "client_order_id": f"manual-{self.n}", "ticker": t, "book_side": side, "p": p, "rem": float(n),
                            "exp": None}
        return oid

    # ---------------------------------------------------------------- the HTTP side
    def verify(self, method, full, h):
        try:
            if h.get("KALSHI-ACCESS-KEY") != self.key_id:
                return "unknown key id"
            ts = h["KALSHI-ACCESS-TIMESTAMP"]
            if abs(int(ts) - self.clock() * 1000) > 30_000:
                return "timestamp too far from Kalshi's clock"
            sig = base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"])
            msg = f"{ts}{method}{full}".encode()
            if isinstance(self.pub, ed25519.Ed25519PublicKey):
                self.pub.verify(sig, msg)
            else:
                self.pub.verify(sig, msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
            return None
        except Exception as e:  # noqa: BLE001
            self.sig_fail += 1
            return f"bad signature ({e.__class__.__name__})"

    def __call__(self, method, url, headers, data, timeout):
        assert url.startswith(self.ROOT + "/trade-api/v2/"), url
        u = urllib.parse.urlsplit(url)
        path = u.path[len("/trade-api/v2"):]
        q = dict(urllib.parse.parse_qsl(u.query))
        body = json.loads(data.decode()) if data else None
        self.calls.append((method, path, q, body, dict(headers)))
        if self.down:
            raise OSError("network is down")
        for (m, pre), (st, code) in list(self.fail.items()):
            if m == method and path.startswith(pre):
                return st, json.dumps({"error": {"code": code, "message": "fake refusal", "details": ""}}).encode()
        if path.startswith("/portfolio"):
            why = self.verify(method, u.path, headers)
            if why:
                return 401, json.dumps({"error": {"code": "unauthorized", "message": why}}).encode()
        try:
            st, j = self.route(method, path, q, body)
        except KeyError:
            st, j = 404, {"error": {"code": "not_found", "message": "no such thing"}}
        return st, json.dumps(j).encode()

    def _order_row(self, o):
        p = o["p"]
        return {"order_id": o["order_id"], "client_order_id": o["client_order_id"], "ticker": o["ticker"], "book_side": o["book_side"],
                "outcome_side": "yes" if o["book_side"] == "bid" else "no", "status": "resting", "type": "limit",
                "yes_price_dollars": f"{p:.4f}", "no_price_dollars": f"{1 - p:.4f}", "remaining_count_fp": f"{o['rem']:.2f}",
                "initial_count_fp": f"{o.get('n', o['rem']):.2f}", "fill_count_fp": "0.00",
                "expiration_time": iso(o["exp"]) if o.get("exp") else None, "created_time": iso(self.clock())}

    def route(self, method, path, q, body):
        now = self.clock()
        if method == "GET":
            if path == "/exchange/status":
                return 200, {"exchange_active": True, "trading_active": self.trading}
            if path == "/portfolio/balance":
                return 200, {"balance": int(round(self.cash * 100)), "balance_dollars": f"{self.cash:.4f}",
                             "portfolio_value": int(round(self.value() * 100)), "updated_ts": int(now)}
            if path == "/portfolio/positions":
                return 200, {"cursor": "", "event_positions": [], "market_positions": [
                    {"ticker": t, "exchange_index": 0, "position_fp": f"{p:.2f}", "market_exposure_dollars": f"{self.cost.get(t, 0):.6f}",
                     "realized_pnl_dollars": "0", "fees_paid_dollars": "0", "total_traded_dollars": "0", "last_updated_ts": iso(now),
                     "netting_enabled": True} for t, p in self.pos.items()]}
            if path == "/portfolio/orders":
                for oid in [i for i, o in self.orders.items() if o.get("exp") and o["exp"] <= now]:
                    self.orders.pop(oid)                                       # expired by Kalshi
                return 200, {"cursor": "", "orders": [self._order_row(o) for o in self.orders.values()]}
            if path == "/portfolio/fills":
                lo = float(q.get("min_ts") or 0)
                return 200, {"cursor": "", "fills": [f for f in self.fills if f["ts"] >= lo]}
            if path == "/portfolio/settlements":
                lo = float(q.get("min_ts") or 0)
                return 200, {"cursor": "", "settlements": [s for s in self.settles if KL._ts(s["settled_time"]) >= lo]}
            if path == "/incentive_programs":
                s = q.get("series_ticker")
                return 200, {"next_cursor": "", "incentive_programs": [p for p in self.programs if p["series_ticker"] == s]}
            if path == "/markets":
                s = q.get("series_ticker")
                return 200, {"cursor": "", "markets": [m for t, m in self.markets.items() if t.startswith(s + "-") and m["status"] == "active"]}
            m = re.fullmatch(r"/markets/([^/]+)(/orderbook)?", path)
            if m:
                t = m.group(1)
                if m.group(2):
                    yes, no = self.books.get(t, ([], []))
                    return 200, {"orderbook_fp": {"yes_dollars": [[f"{p:.4f}", f"{s:.2f}"] for p, s in sorted(yes)],
                                                  "no_dollars": [[f"{p:.4f}", f"{s:.2f}"] for p, s in sorted(no)]}}
                return 200, {"market": self.markets[t]}
        if method == "POST" and path == "/portfolio/events/orders":
            return self.place(body)
        if method == "DELETE":
            if path == "/portfolio/events/orders/batched":
                out = []
                for x in body.get("orders") or []:
                    o = self.orders.pop(x["order_id"], None)
                    out.append({"order_id": x["order_id"], "reduced_by": f"{o['rem'] if o else 0:.2f}",
                                "error": None if o else {"code": "not_found", "message": "gone"}})
                return 200, {"orders": out}
            m = re.fullmatch(r"/portfolio/events/orders/([^/]+)", path)
            if m:
                o = self.orders.pop(m.group(1))
                return 200, {"order_id": o["order_id"], "reduced_by": f"{o['rem']:.2f}", "ts_ms": int(now * 1000)}
        return 404, {"error": {"code": "not_found", "message": f"{method} {path}"}}

    def place(self, b):
        for k in ("ticker", "side", "count", "price", "time_in_force", "self_trade_prevention_type"):
            if k not in b:
                return 400, {"error": {"code": "missing_parameters", "message": k}}
        t, side, tif = b["ticker"], b["side"], b["time_in_force"]
        n, p = float(b["count"]), float(b["price"])
        if side not in ("bid", "ask") or tif not in ("good_till_canceled", "immediate_or_cancel", "fill_or_kill"):
            return 400, {"error": {"code": "invalid_parameters", "message": "side / time_in_force"}}
        if b.get("post_only") and tif != "good_till_canceled":
            return 400, {"error": {"code": "Post_only_but_execution_type_can't_rest"}}
        if b.get("reduce_only") and tif != "immediate_or_cancel":
            return 400, {"error": {"code": "invalid_order", "details": "reduce_only needs immediate_or_cancel"}}
        mk = self.markets.get(t)
        if not mk or mk["status"] != "active":
            return 409, {"error": {"code": "market_inactive"}}
        yes, no = self.books[t]
        bid = max((x for x, _ in yes), default=None)
        ask = (1 - max(x for x, _ in no)) if no else None
        if b.get("post_only") and ((side == "bid" and ask is not None and p >= ask - 1e-9) or (side == "ask" and bid is not None and p <= bid + 1e-9)):
            return 400, {"error": {"code": "invalid_order", "message": "invalid order", "details": "post only cross"}}
        self.n += 1
        oid = f"ord{self.n}"
        if tif == "immediate_or_cancel":
            if b.get("reduce_only"):
                held = self.pos.get(t, 0.0)
                n = min(n, max(held, 0.0)) if side == "ask" else min(n, max(-held, 0.0))
            got = 0.0
            if side == "bid" and ask is not None and p >= ask - 1e-9:
                got, px = n, ask
            elif side == "ask" and bid is not None and p <= bid + 1e-9:
                got, px = n, bid
            if got > 0:
                self.apply_fill(oid, t, side, got, px, True)
            return 201, {"order_id": oid, "fill_count": f"{got:.2f}", "remaining_count": "0.00", "ts_ms": int(self.clock() * 1000),
                         "client_order_id": b.get("client_order_id")}
        self.orders[oid] = {"order_id": oid, "client_order_id": b.get("client_order_id") or "", "ticker": t, "book_side": side, "p": p,
                            "rem": n, "n": n, "exp": b.get("expiration_time"), "body": b}
        return 201, {"order_id": oid, "fill_count": "0.00", "remaining_count": f"{n:.2f}", "ts_ms": int(self.clock() * 1000),
                     "client_order_id": b.get("client_order_id")}


# ================================================================================================ the test world
def keypair(kind="rsa"):
    if kind == "ed":
        k = ed25519.Ed25519PrivateKey.generate()
        pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    else:
        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
    return k, pem


class World:
    """A temp OLYMPUS_HOME with the key outside the repo, a temp state dir, the fixture plan copied (so a test may edit it)."""

    def __init__(self, tmp, name, kind="ed", cash=100.0, candidates=True, plan_edit=None):
        self.dir = os.path.join(tmp, name)
        os.makedirs(self.dir)
        self.home = os.path.join(self.dir, "home")
        kd = os.path.join(self.home, "kalshi")
        os.makedirs(kd)
        self.key, pem = keypair(kind)
        with open(os.path.join(kd, "kalshi_key.pem"), "wb") as fh:
            fh.write(pem.replace(b"\n", b"\r\n"))                        # as Windows saves the downloaded .txt
        with open(os.path.join(kd, "key_id.txt"), "w", encoding="utf-8-sig") as fh:
            fh.write(KEY_ID + "\n")
        self.env = {"OLYMPUS_HOME": self.home, "LE_KALSHI_CLOCK": "0"}
        self.sd = os.path.join(self.dir, "state")
        self.plan = os.path.join(self.dir, "plan.json")
        raw = json.load(open(PLAN, encoding="utf-8"))
        if plan_edit:
            plan_edit(raw)
        json.dump(raw, open(self.plan, "w", encoding="utf-8"))
        self.cands = os.path.join(self.dir, "cands")
        os.makedirs(self.cands)
        if candidates:
            for fn in os.listdir(CANDS):
                shutil.copy(os.path.join(CANDS, fn), self.cands)
        self.clock = Clock()
        self.fake = FakeKalshi(self.clock, self.key.public_key(), cash=cash)
        f = self.fake
        f.market("KXFAKEA-26NOV25-T1", [(0.40, 300), (0.39, 500)], [(0.55, 400), (0.54, 600)])
        f.market("KXFAKEA-26NOV25-T2", [(0.30, 1000)], [(0.60, 1000)])
        f.market("KXFAKEA-26NOV25-T3", [(0.20, 1000)], [(0.70, 1000)])
        f.market("KXFAKEB-26NOV30-X1", [(0.50, 500)], [(0.45, 500)])
        f.market("KXFAKET-26NOV18-Y1", [(0.88, 100)], [(0.10, 100)], close_h=3)
        f.program("KXFAKEA-26NOV25-T1", 30)
        f.program("KXFAKEA-26NOV25-T2", 20)
        f.program("KXFAKEA-26NOV25-T3", 10)
        f.program("KXFAKEB-26NOV30-X1", 15, target=500)
        self.pushes = []

    def poster(self, base, topic, msg):
        self.pushes.append(dict(msg, t=self.clock()))
        return True

    def api(self, key=None):
        return KL.Api(key_id=KEY_ID, key=key or self.key, http=self.fake, sleep=lambda s: None, clock=self.clock, gap=0)

    def arm(self):
        return KL.arm(KL.PHRASE, state_dir=self.sd, plan_path=self.plan, cand_dir=self.cands, env=self.env, now=self.clock())

    def ex(self, api=None, env=None):
        return KL.Executor(api or self.api(), state_dir=self.sd, plan_path=self.plan, cand_dir=self.cands, env=env or self.env,
                           clock=self.clock, poster=self.poster, alert_cfg=ALERT)

    def arm_rec(self):
        return json.load(open(KL.paths(self.sd)["arm"], encoding="utf-8"))

    def stops(self):
        return [p for p in self.pushes if p["title"].startswith("Kalshi STOPPED")]


# ================================================================================================ a. signing
def part_signing(tmp):
    w = World(tmp, "sign_rsa", kind="rsa")
    api = KL.api_from_key(w.env, http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0)
    b = api.get("/portfolio/balance", {"x": 1})
    _m, path, q, _b, h = w.fake.calls[-1]
    check("a1. RSA-PSS: the key from OLYMPUS_HOME\\kalshi (CRLF + BOM file) signs; the fake verifies ts + GET + /trade-api/v2/portfolio/balance "
          "(the query is not signed)", b.get("balance") == 10000 and w.fake.sig_fail == 0 and q == {"x": "1"}
          and h.get("KALSHI-ACCESS-KEY") == KEY_ID and abs(int(h["KALSHI-ACCESS-TIMESTAMP"]) - w.clock() * 1000) < 2, (b, w.fake.sig_fail))
    w2 = World(tmp, "sign_ed", kind="ed")
    api2 = KL.api_from_key(w2.env, http=w2.fake, sleep=lambda s: None, clock=w2.clock, gap=0)
    r = api2.call("POST", "/portfolio/events/orders", body={"ticker": "KXFAKEA-26NOV25-T1", "side": "bid", "count": "1", "price": "0.3000",
                                                             "time_in_force": "good_till_canceled", "self_trade_prevention_type": "taker_at_cross",
                                                             "post_only": True})
    check("a2. Ed25519 (Kalshi's default key type) signs a POST too; the fake accepts it", r.get("order_id") and w2.fake.sig_fail == 0, r)
    bad = KL.Api(key_id=KEY_ID, key=keypair("ed")[0], http=w2.fake, sleep=lambda s: None, clock=w2.clock, gap=0)
    try:
        bad.get("/portfolio/balance")
        e = None
    except KL.KalshiError as x:
        e = x
    check("a3. a wrong key = HTTP 401 from Kalshi, as a KalshiError (status 401), never a crash", e is not None and e.status == 401, e)
    refused = []
    for m, p in (("POST", "/portfolio/orders"), ("DELETE", "/portfolio/orders/abc"), ("GET", "/api_keys"), ("POST", "/portfolio/transfer"),
                 ("POST", "/portfolio/subaccounts/transfer"), ("GET", "/portfolio/orders?status=resting"), ("GET", "/markets/../portfolio"),
                 ("PUT", "/portfolio/events/orders/x"), ("POST", "/portfolio/events/orders/batched"), ("DELETE", "/portfolio/positions")):
        try:
            api.call(m, p)
            refused.append(False)
        except KL.KalshiError as x:
            refused.append(x.code == "refused")
    n0 = len(w.fake.calls)
    check("a4. only the allow-listed calls exist: the v1 order endpoints, transfers, API keys, PUT, odd paths are refused before any "
          "request (no request sent)", all(refused) and len(w.fake.calls) == n0, refused)
    ok_hosts = all(KL.check_base(f"https://{h}/trade-api/v2") for h in KL.API_HOSTS)
    bad_hosts = 0
    for b_ in ("https://evil.example/trade-api/v2", "http://api.elections.kalshi.com/trade-api/v2", "https://api.elections.kalshi.com/other",
               "https://user:pw@api.elections.kalshi.com/trade-api/v2", "https://api.elections.kalshi.com:8443/trade-api/v2"):
        try:
            KL.check_base(b_)
        except KL.KalshiError:
            bad_hosts += 1
    check("a5. Kalshi's hosts only (production + demo, https, port 443, /trade-api/v2); anything else refused", ok_hosts and bad_hosts == 5, bad_hosts)
    nokey = KL.Api(http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0)
    try:
        nokey.get("/portfolio/balance")
        e = None
    except KL.KalshiError as x:
        e = x
    pub = nokey.get("/markets/KXFAKEA-26NOV25-T1/orderbook", auth=False)
    check("a6. no key: a signed call refuses itself (no request), public prices still work (the dry run)",
          e is not None and e.code == "no_key" and pub.get("orderbook_fp"), e)
    kpath = os.path.join(w.home, "kalshi", "kalshi_key.pem")
    red = KL.redact(f"KALSHI-ACCESS-KEY: {KEY_ID} KALSHI-ACCESS-SIGNATURE: {'Q' * 344} at {kpath} -----BEGIN RSA PRIVATE KEY-----\nMIIE\n"
                    "-----END RSA PRIVATE KEY-----", (KEY_ID, kpath))
    check("a7. error text never shows the key id, a signature, the key path or PEM text", KEY_ID not in red and "Q" * 60 not in red
          and kpath not in red and "MIIE" not in red, red)
    inrepo = os.path.join(ROOT, "tests", "fixtures", "kalshi_live", "not_a_key.pem")
    try:
        KL.load_key(inrepo)
        e = None
    except KL.KalshiError as x:
        e = x
    check("a8. a key file inside the bot folder is refused (it must live outside the repo)", e is not None and e.code == "key_in_repo", e)
    w2.fake.down = True
    try:
        api2.get("/portfolio/balance")
        e = None
    except KL.KalshiError as x:
        e = x
    check("a9. Kalshi unreachable = a KalshiError 'network' (the loop counts it), never an exception into the caller",
          e is not None and e.code == "network", e)


# ================================================================================================ b. plan
def part_plan(tmp):
    raw = json.load(open(PLAN, encoding="utf-8"))
    plan, probs = KL.validate_plan(raw)
    check("b1. the fixture plan validates: 2 series, caps $60 / $20 / -$8 / 8 orders, pause rules parsed (move 5c / 60 min, close 2 h, "
          "spread 10c)", not probs and plan["caps"] == {"capital_cap_usd": 60, "per_market_cap_usd": 20, "daily_loss_stop_usd": 8, "max_open_orders": 8}
          and plan["markets"][0]["pause"] == [{"type": "after_move", "cents": 5.0, "minutes": 60.0}, {"type": "before_close", "hours": 2.0}]
          and plan["markets"][1]["pause"] == [{"type": "wide_spread", "cents": 10.0}], (probs, plan and plan["markets"]))
    cases = {"capital above the $250 ceiling": dict(raw, capital_cap_usd=500), "per market above $50": dict(raw, per_market_cap_usd=80),
             "stop above $25": dict(raw, daily_loss_stop_usd=40), "no stop": {k: v for k, v in raw.items() if k != "daily_loss_stop_usd"},
             "status rejected": dict(raw, status="rejected"), "status PAPER ONLY": dict(raw, status="PAPER ONLY - weak"),
             "another strategy": dict(raw, strategy="martingale"), "no market": dict(raw, markets=[]), "version 2": dict(raw, version=2),
             "size 500": dict(raw, markets=[dict(raw["markets"][0], quote={"offset_cents": 0, "size": 500})]),
             "per market above capital": dict(raw, per_market_cap_usd=20, capital_cap_usd=10)}
    bad = {k: bool(KL.validate_plan(v)[1]) for k, v in cases.items()}
    check("b2. caps above the code's hard ceilings, a bad status, no stop, another strategy, no market, a huge size = problems (it "
          "cannot be armed; never silently clamped)", all(bad.values()), bad)
    odd = dict(raw, markets=[dict(raw["markets"][0], pause=["when the moon is full"])])
    p2, pr2 = KL.validate_plan(odd)
    o, why = KL.rewards_orders(p2["markets"][0], {"start": T0 - 10, "end": T0 + 86400, "target": 1000}, {"ticker": "KXFAKEA-1", "status": "active",
                               "close_ts": T0 + 86400}, [(0.4, 500)], [(0.55, 500)], T0)
    check("b3. a pause rule it does not understand = that market is skipped (fail closed), said in plain words", not pr2 and o == []
          and "not understood" in why, (pr2, why))
    A = KL.load_all(PLAN, CANDS)
    check("b4. candidates: the 'proposal' taker rule is runnable, the 'PAPER ONLY' one is listed as not traded; one hash covers plan + candidates",
          [c["name"] for c in A["cands"]] == ["fav_fixture"] and any("paper_only" in s for s in A["skipped"]) and A["runnable"] and len(A["sha"]) == 64,
          (A["cands"], A["skipped"]))
    w = World(tmp, "plan_sha")
    s1 = KL.load_all(w.plan, w.cands)["sha"]
    with open(os.path.join(w.cands, "fav_fixture.json"), "a", encoding="utf-8") as fh:
        fh.write("\n")
    s2 = KL.load_all(w.plan, w.cands)["sha"]
    check("b5. any change to the plan or a candidate file changes the hash the owner armed", s1 != s2 and s2)
    check("b6. no plan file and no candidate = nothing runnable", not KL.load_all(os.path.join(tmp, "none.json"), os.path.join(tmp, "nodir"))["runnable"])
    forms = {"close_2h": ("before_close", 2), "pull quotes 1 h before the close": ("before_close", 1), "pause 60 min after a 5c move": ("after_move", 60),
             "move_5c_1h": ("after_move", 60), "spread_10c": ("wide_spread", 10), "program_end_30m": ("program_end", 30)}
    got = {k: KL.parse_pause([k])[0] for k in forms}
    okf = all(g and g[0]["type"] == forms[k][0] and forms[k][1] in g[0].values() for k, g in got.items())
    dicts = KL.parse_pause([{"hours_before_close": 3}, {"move_cents": 5, "minutes": 60}, {"spread_cents": 8},
                            {"type": "after_move", "cents": 5, "hours": 1}])
    check("b7. the pause rules the research helpers may write are read in several forms (strings and dicts), each to the same meaning",
          okf and not dicts[1] and [d["type"] for d in dicts[0]] == ["before_close", "after_move", "wide_spread", "after_move"], (got, dicts))


# ================================================================================================ c. caps (pure)
def base_view(now=T0):
    book = {"t": now, "yes": [(0.40, 300)], "no": [(0.55, 400)]}
    return {"now": now, "kill": False, "live": True, "why_not_live": "", "paused": False, "stopped": False,
            "caps": {"capital_cap_usd": 60.0, "per_market_cap_usd": 20.0, "daily_loss_stop_usd": 8.0, "max_open_orders": 8, "size": 100},
            "balance": 100.0, "resting": [], "open_orders": 0, "exposure": {}, "pos": {}, "day_pnl": 0.0, "orders_last_min": 0,
            "orders_today": 0, "markets": {"KXA-1": {"status": "active", "close_ts": now + 86400}}, "books": {"KXA-1": book}}


def quote(**kw):
    o = {"ticker": "KXA-1", "book": "bid", "price": 0.40, "count": 10, "kind": "quote", "post_only": True, "tif": "good_till_canceled",
         "expires": T0 + 1200}
    o.update(kw)
    return o


def part_caps(tmp):
    ok = KL.check_order(quote(), base_view())
    check("c0. a good maker quote passes every check", ok[0], ok)
    rest = [{"id": "r1", "coid": "olyk-1", "ticker": "KXA-1", "book": "bid", "price": 0.30, "remaining": 40.0}]
    cases = [
        ("KILL", {}, {"kill": True}), ("NOT_ARMED", {}, {"live": False}), ("STOPPED", {}, {"stopped": True}), ("PAUSED", {}, {"paused": True}),
        ("NOT_MAKER", {"post_only": False}, {}), ("NOT_MAKER", {"tif": "immediate_or_cancel"}, {}), ("EXPIRY", {"expires": T0 + 7200}, {}),
        ("EXPIRY", {"expires": None}, {}), ("PRICE", {"price": 0.01}, {}), ("PRICE", {"price": 0.99, "book": "ask"}, {}),
        ("SIZE", {"count": 101}, {}), ("BAD_ORDER", {"count": 2.5}, {}), ("BAD_ORDER", {"ticker": "x y"}, {}),
        ("MARKET_CLOSED", {}, {"markets": {"KXA-1": {"status": "closed", "close_ts": T0 + 86400}}}),
        ("MARKET_CLOSED", {}, {"markets": {"KXA-1": {"status": "active", "close_ts": T0 + 30}}}),
        ("STALE_BOOK", {}, {"books": {"KXA-1": {"t": T0 - 200, "yes": [(0.40, 300)], "no": [(0.55, 400)]}}}),
        ("CROSS", {"price": 0.45}, {}), ("CROSS", {"book": "ask", "price": 0.40}, {}),
        ("MARKET_CAP", {"count": 25}, {"resting": rest, "open_orders": 1}),                      # $12 resting + $10 > $20
        ("MARKET_CAP", {}, {"exposure": {"KXA-1": 17.0}}),
        ("CAPITAL_CAP", {}, {"exposure": {"KXB-9": 57.0}}),                                     # $57 + $4 > $60
        ("BALANCE", {}, {"balance": 3.0}), ("OPEN_ORDERS", {}, {"open_orders": 8}),
        ("DAY_STOP", {}, {"day_pnl": -8.0}), ("STOP_ROOM", {}, {"day_pnl": -5.0}),                # $4 order, $3 room
        ("RATE", {}, {"orders_last_min": 30}), ("DAY_ORDERS", {}, {"orders_today": 1500}),
        ("BAND", {"kind": "taker", "tif": "immediate_or_cancel", "post_only": False, "band": (0.8, 0.95), "price": 0.45, "expires": None}, {}),
        ("NOT_HELD", {"kind": "flatten", "tif": "immediate_or_cancel", "reduce_only": True, "post_only": False, "book": "ask"}, {"pos": {}}),
        ("NOT_HELD", {"kind": "flatten", "tif": "immediate_or_cancel", "reduce_only": True, "post_only": False, "book": "ask", "count": 9},
         {"pos": {"KXA-1": 5.0}}),
        ("ERROR", {}, {"caps": None}),
    ]
    got = []
    for code, o_kw, v_kw in cases:
        v = base_view()
        v.update(v_kw)
        r = KL.check_order(quote(**o_kw), v)
        got.append((code, r[1], r[0]))
    bad = [g for g in got if g[0] != g[1] or g[2]]
    check(f"c1. each cap blocks an order on its own ({len(cases)} cases: kill, not armed, stopped, paused, not post-only, expiry, price, size, "
          "market closed, stale book, cross, per-market, capital, cash, open orders, day stop, stop room, rate, day orders, taker band, "
          "flatten not held, a broken view)", not bad, bad)
    v = base_view()
    v.update(kill=True, live=False, stopped=True, paused=True, pos={"KXA-1": 5.0})
    fl = KL.check_order(quote(kind="flatten", tif="immediate_or_cancel", reduce_only=True, post_only=False, book="ask", count=5), v)
    check("c2. a reduce-only immediate-or-cancel CLOSE of what Kalshi holds passes even when killed / stopped / paused (it only lowers risk)", fl[0], fl)
    words = [KL.check_order(quote(**o_kw), dict(base_view(), **v_kw))[2] for _c, o_kw, v_kw in cases[:6]]
    check("c3. every block says why in plain words", all(isinstance(x, str) and len(x) > 8 for x in words), words)


# ================================================================================================ d. arming
def part_arming(tmp):
    w = World(tmp, "arm")
    live, why = KL.arm_state(state_dir=w.sd)
    check("d1. OFF by default: no arm record = not live ('not armed (OFF is the default)')", not live and "OFF is the default" in why, why)
    r1 = KL.arm("I ACCEPT LIVE RISK", state_dir=w.sd, plan_path=w.plan, cand_dir=w.cands, env=w.env, now=w.clock())
    r2 = KL.arm("i accept kalshi live risk", state_dir=w.sd, plan_path=w.plan, cand_dir=w.cands, env=w.env, now=w.clock())
    r3 = KL.arm(KL.PHRASE, state_dir=w.sd, plan_path=w.plan, cand_dir=w.cands, env=dict(w.env, LE_KALSHI_LIVE="0"), now=w.clock())
    check("d2. the futures phrase, a lower-case phrase and LE_KALSHI_LIVE=0 never arm", not r1[0] and not r2[0] and not r3[0]
          and not os.path.exists(KL.paths(w.sd)["arm"]), (r1, r2, r3))
    os.makedirs(w.sd, exist_ok=True)
    open(KL.paths(w.sd)["kill"], "w").write("old kill")
    ok = w.arm()
    rec = w.arm_rec()
    raw = open(KL.paths(w.sd)["arm"], encoding="utf-8").read()
    sha = KL.load_all(w.plan, w.cands)["sha"]
    check("d3. the exact phrase arms (and clears an old kill switch); the record holds a proof hash, never the phrase itself",
          ok[0] and rec["armed"] is True and KL.PHRASE not in raw and "ACCEPT" not in raw and len(rec["proof"]) == 64
          and not os.path.exists(KL.paths(w.sd)["kill"]) and KL.arm_state(state_dir=w.sd, sha=sha, env=w.env)[0], (ok, rec))
    check("d4. LE_KALSHI_LIVE=0 switches an armed PC off", not KL.arm_state(state_dir=w.sd, sha=sha, env={"LE_KALSHI_LIVE": "0"})[0])
    raw2 = json.load(open(w.plan, encoding="utf-8"))
    raw2["daily_loss_stop_usd"] = 7
    json.dump(raw2, open(w.plan, "w", encoding="utf-8"))
    sha2 = KL.load_all(w.plan, w.cands)["sha"]
    l2, why2 = KL.arm_state(state_dir=w.sd, sha=sha2, env=w.env)
    check("d5. a plan change after arming = not live ('the plan changed since you armed it')", not l2 and "plan changed" in why2, why2)
    rec2 = dict(rec, exec="2020-01-01.0")
    KL._jwrite(KL.paths(w.sd)["arm"], rec2)
    l3, why3 = KL.arm_state(state_dir=w.sd, env=w.env)
    KL._jwrite(KL.paths(w.sd)["arm"], dict(rec, proof="0" * 64))
    l4, why4 = KL.arm_state(state_dir=w.sd, env=w.env)
    KL._jwrite(KL.paths(w.sd)["arm"], {"armed": True})
    l5, _ = KL.arm_state(state_dir=w.sd, env=w.env)
    check("d6. a new executor version, a forged proof or a hand-written {armed: true} = not live", not l3 and "updated" in why3 and not l4
          and "phrase" in why4 and not l5, (why3, why4))
    w2 = World(tmp, "arm_bad", plan_edit=lambda r: r.update(capital_cap_usd=900))
    r4 = w2.arm()
    check("d7. a plan above the hard ceilings cannot be armed, even with the phrase", not r4[0] and "ceiling" in r4[1], r4)

    def go(wg, typed, **kw):
        said, spawned = [], []

        def inp(_prompt):
            return typed() if callable(typed) else typed
        rc = KL.go(state_dir=wg.sd, env=wg.env, input_fn=inp, say=said.append, spawn_fn=lambda sd: spawned.append(sd) or 4242, api=kw.get("api") or wg.api(),
                   dry_api=KL.Api(http=wg.fake, sleep=lambda s: None, clock=wg.clock, gap=0), plan_path=wg.plan, cand_dir=wg.cands,
                   poster=wg.poster, alert_cfg=ALERT, now=wg.clock())
        return rc, "\n".join(said), spawned
    wg = World(tmp, "go_wrong")
    rc, txt, sp = go(wg, "I ACCEPT LIVE RISK")
    check("d8. KALSHI_LIVE.bat (--go): it shows the plan, the limits, the key check and the dry run, then a WRONG phrase arms nothing and "
          "starts nothing", rc == 1 and not sp and not KL.arm_state(state_dir=wg.sd)[0] and "Limits (checked before every order)" in txt
          and "The key works" in txt and "would rest" in txt and "Nothing is armed" in txt and not wg.fake.posts(), txt[-400:])
    wg = World(tmp, "go_right")
    rc, txt, sp = go(wg, KL.PHRASE)
    armed = [p for p in wg.pushes if p["title"].startswith("Kalshi LIVE armed")]
    check("d9. the exact phrase typed: armed, the loop started once in the background, ONE 'armed' push; still no order from go itself",
          rc == 0 and sp == [wg.sd] and KL.arm_state(state_dir=wg.sd)[0] and len(armed) == 1 and not wg.fake.posts(), (rc, sp, txt[-300:]))
    wg = World(tmp, "go_nokey")
    os.remove(os.path.join(wg.home, "kalshi", "kalshi_key.pem"))
    try:
        rc = KL.go(state_dir=wg.sd, env=wg.env, input_fn=lambda _p: KL.PHRASE, say=lambda *_: None, spawn_fn=lambda sd: 1,
                   plan_path=wg.plan, cand_dir=wg.cands, now=wg.clock())
        crashed = False
    except Exception:  # noqa: BLE001
        rc, crashed = None, True
    check("d10. no key on the PC: one [FIX] (KALSHI_KEY_SETUP.bat), nothing armed, no crash", rc == 1 and not crashed
          and not KL.arm_state(state_dir=wg.sd)[0], rc)
    wg = World(tmp, "go_changed")

    def sneaky():
        raw = json.load(open(wg.plan, encoding="utf-8"))
        raw["per_market_cap_usd"] = 19
        json.dump(raw, open(wg.plan, "w", encoding="utf-8"))
        return KL.PHRASE
    rc, txt, sp = go(wg, sneaky)
    check("d11. the plan changed between the screen and the phrase: refused (he arms only what he saw)", rc == 1 and not sp
          and "changed while you were reading" in txt and not KL.arm_state(state_dir=wg.sd)[0], txt[-300:])


# ================================================================================================ e. the loop on the fake Kalshi
def part_loop(tmp):
    w = World(tmp, "loop")
    f = w.fake
    w.arm()
    eq0 = f.equity()
    ex = w.ex()
    out = ex.cycle()
    ours = sorted(((o["ticker"], o["book_side"], round(o["p"], 2), o["rem"]) for o in f.ours()))
    want = [("KXFAKEA-26NOV25-T1", "ask", 0.45, 10.0), ("KXFAKEA-26NOV25-T1", "bid", 0.40, 10.0), ("KXFAKEA-26NOV25-T2", "ask", 0.40, 10.0),
            ("KXFAKEA-26NOV25-T2", "bid", 0.30, 10.0), ("KXFAKEB-26NOV30-X1", "ask", 0.56, 5.0), ("KXFAKEB-26NOV30-X1", "bid", 0.49, 5.0)]
    check("e1. armed: one loop rests one quote per side on the 2 biggest rewarded KXFAKEA markets + the KXFAKEB one (1c behind), "
          "at the reward reference price, the plan's sizes; the smallest pool (T3) is left out", ours == want and out.get("placed") == 7,
          (ours, out))
    bodies = [c[3] for c in f.posts() if c[3].get("post_only")]
    now = w.clock()
    good = all(b["time_in_force"] == "good_till_canceled" and b["post_only"] is True and b["cancel_order_on_pause"] is True
               and now < b["expiration_time"] <= now + KL.ORDER_TTL_S and b["client_order_id"].startswith("olyk-")
               and b["self_trade_prevention_type"] == "taker_at_cross" and re.fullmatch(r"\d+", b["count"])
               and re.fullmatch(r"0\.\d{4}", b["price"]) and b["side"] in ("bid", "ask") and "reduce_only" not in b for b in bodies)
    check("e2. every quote is a V2 order (POST /portfolio/events/orders): side bid/ask, count + price strings, post-only, good-till-canceled, "
          "expiring within 20 min (dead-man switch), cancel_order_on_pause, olyk- client id", len(bodies) == 6 and good, bodies[:2])
    tk = [c[3] for c in f.posts() if c[3].get("time_in_force") == "immediate_or_cancel"]
    check("e3. the taker candidate: ONE limit immediate-or-cancel buy of YES at the 90c ask on the market closing in 3 h (5 contracts = $4.50); "
          "never a market order", len(tk) == 1 and tk[0]["side"] == "bid" and tk[0]["price"] == "0.9000" and tk[0]["count"] == "5"
          and f.pos.get("KXFAKET-26NOV18-Y1") == 5.0 and "type" not in tk[0], tk)
    n_calls = len(f.calls)
    w.clock.add(60)
    out2 = ex.cycle()
    check("e4. nothing moved: the next loop keeps every order (no cancel, no new order) and does not bet the taker market twice",
          not f.posts(n_calls) and not f.deletes(n_calls) and out2.get("placed") == 0, (out2, f.posts(n_calls)))
    old = {o["order_id"] for o in f.ours()}
    f.books["KXFAKEA-26NOV25-T1"] = ([(0.41, 300), (0.39, 500)], [(0.55, 400)])
    n_calls = len(f.calls)
    w.clock.add(60)
    ex.cycle()
    t1 = sorted((o["book_side"], round(o["p"], 2)) for o in f.ours() if o["ticker"] == "KXFAKEA-26NOV25-T1")
    check("e5. the YES bid moved up 1c: only that quote is cancelled and re-placed at 41c; the other five stay",
          t1 == [("ask", 0.45), ("bid", 0.41)] and len(f.deletes(n_calls)) == 1 and len(f.posts(n_calls)) == 1
          and len(old & {o["order_id"] for o in f.ours()}) == 5, (t1, f.deletes(n_calls), f.posts(n_calls)))
    bid = next(o for o in f.ours() if o["ticker"] == "KXFAKEA-26NOV25-T1" and o["book_side"] == "bid")
    f.fill(bid["order_id"], 10)
    ask = next(o for o in f.ours() if o["ticker"] == "KXFAKEB-26NOV30-X1" and o["book_side"] == "ask")
    f.fill(ask["order_id"], 5)
    w.clock.add(60)
    out3 = ex.cycle()
    true_pnl = f.equity() - eq0
    check("e6. two fills (10 YES at 41c, 5 NO at 44c) + the taker's 5 YES: the day P&L (signed contracts at the mid) = the fake's own "
          "real-model accounting (cash + YES/NO legs at the mid) to the cent", abs(out3["day_pnl"] - true_pnl) < 0.011
          and ex.st["fills_today"] == 3, (out3, round(true_pnl, 4), ex.st["fills_today"]))
    check("e7. after a fill the loop keeps quoting within the per-market cap: the market's resting + held $ stays <= $20",
          KL.used_market(ex.v, "KXFAKEA-26NOV25-T1") <= 20.0 + 1e-9 and KL.used_total(ex.v) <= 60 + 1e-9, KL.used_market(ex.v, "KXFAKEA-26NOV25-T1"))
    f.settle("KXFAKET-26NOV18-Y1", "yes")
    w.clock.add(60)
    out4 = ex.cycle()
    true_pnl = f.equity() - eq0
    check("e8. the taker market settles YES ($5 paid): the day P&L still = the fake's accounting, positions still match (no mismatch)",
          abs(out4["day_pnl"] - true_pnl) < 0.011 and ex.st["mismatch"] == 0 and not ex.done, (out4, round(true_pnl, 4), ex.st["mismatch"]))
    st = json.load(open(KL.paths(w.sd)["state"], encoding="utf-8"))
    st["orders"] = {}
    json.dump(st, open(KL.paths(w.sd)["state"], "w", encoding="utf-8"))
    n_calls = len(f.calls)
    w.clock.add(60)
    ex2 = w.ex()                                            # a restart that lost its order list
    ex2.cycle()
    pairs = [(o["ticker"], o["book_side"]) for o in f.ours()]
    check("e9. restart: the new loop ADOPTS the resting olyk- orders from Kalshi (no duplicates, no new quotes on the same sides)",
          len(pairs) == len(set(pairs)) and len(ex2.st["orders"]) == len(pairs) and not f.posts(n_calls), (pairs, f.posts(n_calls)))
    fid = f.foreign("KXFAKEA-26NOV25-T2", "bid", 0.20, 10)
    w.clock.add(60)
    ex2.cycle()
    check("e10. a foreign (not olyk-) order counts in the caps ($2 more in that market) and is never cancelled by a re-quote",
          fid in f.orders and any(o["id"] == fid for o in ex2.v["resting"]), fid in f.orders)
    old = {o["order_id"] for o in f.ours()}
    w.clock.add(16 * 60)
    ex2.cycle()
    new = {o["order_id"] for o in f.ours()}
    check("e11. 16 minutes later (under 5 min left on each order): every quote is renewed (cancel + new expiry), the foreign one untouched",
          old and not (old & new) and len(new) == len(old) and fid in f.orders, (len(old), len(new)))
    return w


# ================================================================================================ f. stops
def loss_world(tmp, name):
    w = World(tmp, name, candidates=False)
    w.arm()
    ex = w.ex()
    ex.cycle()
    for o in list(w.fake.ours()):
        if o["book_side"] == "bid":
            w.fake.fill(o["order_id"])
    for t in list(w.fake.books):
        w.fake.books[t] = ([(0.03, 100)], [(0.96, 100)])
    return w, ex


def part_stops(tmp):
    w, ex = loss_world(tmp, "stop_loss")
    fid = w.fake.foreign("KXFAKEA-26NOV25-T3", "bid", 0.10, 5)
    w.clock.add(60)
    out = ex.cycle()
    rec = w.arm_rec()
    st = w.stops()
    check("f1. daily loss stop: day <= -$8 -> every olyk- order cancelled (the foreign one kept), OFF (armed false + the reason), "
          "one HIGH push at once, the loop ends", out["day_pnl"] <= -8 and not w.fake.ours() and fid in w.fake.orders and rec["armed"] is False
          and "daily loss stop" in rec["stopped"] and len(st) == 1 and st[0]["priority"] == "high" and ex.done, (out, rec, st))
    n = len(w.fake.calls)
    ex2 = w.ex()
    ex2.cycle()
    check("f2. re-arms OFF: a new loop after the stop places nothing (not armed); maybe_run does not restart it",
          not w.fake.posts(n) and ex2.done and KL.maybe_run(say=lambda *_: None, state_dir=w.sd, now=w.clock(), spawn_fn=lambda sd: 1) is None)
    r = w.arm()
    check("f3. the same ET day, even the typed phrase cannot re-arm after the loss stop ('try again tomorrow')", not r[0] and "tomorrow" in r[1], r)

    w = World(tmp, "stop_kill", candidates=False)
    w.arm()
    ex = w.ex()
    ex.cycle()
    fid = w.fake.foreign("KXFAKEA-26NOV25-T3", "bid", 0.10, 5)
    open(KL.paths(w.sd)["kill"], "w").write("kill")
    w.clock.add(60)
    ex.cycle()
    check("f4. the kill switch file: EVERY resting order cancelled (the foreign one too), OFF, one push", not w.fake.orders and ex.done
          and w.arm_rec()["armed"] is False and len(w.stops()) == 1, (w.fake.orders, w.stops()))

    w = World(tmp, "stop_phone", candidates=False)
    w.arm()
    ex = w.ex()
    ex.cycle()
    said = KL.phone_press("pause", now=w.clock(), state_dir=w.sd, env=w.env)
    n = len(w.fake.calls)
    w.clock.add(60)
    ex.cycle()
    w.clock.add(60)
    ex.cycle()
    card = KL.read_card(now=w.clock(), state_dir=w.sd)
    check("f5. phone PAUSE: our quotes cancelled, no new order while paused (until 4 PM ET), still armed; the card says paused",
          "paused" in said and not w.fake.ours() and not w.fake.posts(n) and w.arm_rec()["armed"] is True and card["st"] == "paused", (said, card))
    KL.phone_press("resume", now=w.clock(), state_dir=w.sd, env=w.env)
    w.clock.add(60)
    ex.cycle()
    check("f6. phone RESUME lifts it: the quotes come back (it never arms: it only lifts the pause)", len(w.fake.ours()) == 6, len(w.fake.ours()))
    for o in [x for x in w.fake.ours() if x["book_side"] == "bid"][:2]:
        w.fake.fill(o["order_id"])
    w.clock.add(60)
    ex.cycle()
    held = dict(w.fake.pos)
    said = KL.phone_press("flatten", now=w.clock(), state_dir=w.sd, env=w.env)
    off_now = w.arm_rec()["armed"] is False
    n = len(w.fake.calls)
    w.clock.add(30)
    ex.cycle()
    closes = [c[3] for c in w.fake.posts(n)]
    check("f7. phone FLATTEN: OFF at once (before the loop even runs), then every order cancelled + what Kalshi holds sold with "
          "reduce-only immediate-or-cancel orders; nothing held after; one push", held and off_now and not w.fake.orders and not w.fake.pos
          and closes and all(b.get("reduce_only") is True and b["time_in_force"] == "immediate_or_cancel" and not b.get("post_only") for b in closes)
          and ex.done and len(w.stops()) == 1 and "flatten" in said, (held, closes, w.fake.pos, w.stops()))

    w = World(tmp, "stop_phone_kill", candidates=False)
    w.arm()
    ex = w.ex()
    ex.cycle()
    KL.phone_press("kill", now=w.clock(), state_dir=w.sd, env=w.env)
    w.clock.add(30)
    ex.cycle()
    check("f8. phone KILL: the kill switch file + OFF + everything cancelled; arming again needs the typed phrase",
          os.path.exists(KL.paths(w.sd)["kill"]) and not w.fake.orders and ex.done and not KL.arm_state(state_dir=w.sd)[0])

    w = World(tmp, "stop_plan", candidates=False)
    w.arm()
    ex = w.ex()
    ex.cycle()
    raw = json.load(open(w.plan, encoding="utf-8"))
    raw["markets"][0]["quote"]["size"] = 20
    json.dump(raw, open(w.plan, "w", encoding="utf-8"))
    w.clock.add(60)
    ex.cycle()
    check("f9. the plan file changes while live: stop, our orders cancelled, OFF ('the plan changed'), one push",
          ex.done and not w.fake.ours() and "plan changed" in w.arm_rec()["stopped"] and len(w.stops()) == 1, w.arm_rec())

    w = World(tmp, "stop_rejects", candidates=False)
    w.arm()
    w.fake.fail[("POST", "/portfolio/events/orders")] = (400, "invalid_parameters")
    ex = w.ex()
    ex.cycle()
    check("f10. Kalshi refuses 3 orders in a row: stop + OFF ('refused 3 orders in a row')", ex.done and "refused 3 orders" in w.arm_rec()["stopped"]
          and len(w.fake.posts()) == 3, (w.arm_rec(), len(w.fake.posts())))

    w = World(tmp, "stop_410", candidates=False)
    w.arm()
    w.fake.fail[("POST", "/portfolio/events/orders")] = (410, "deprecated_v1_order_endpoint")
    ex = w.ex()
    ex.cycle()
    check("f11. HTTP 410 (Kalshi changed its order API): stop at the first order", ex.done and "410" in w.arm_rec()["stopped"]
          and len(w.fake.posts()) == 1, w.arm_rec())

    w = World(tmp, "stop_401", candidates=False)
    w.arm()
    ex = w.ex(api=w.api(key=keypair("ed")[0]))
    ex.cycle()
    check("f12. Kalshi refuses the key (401): stop + OFF ('refused the key'), nothing sent", ex.done and "refused the key" in w.arm_rec()["stopped"]
          and not w.fake.posts(), w.arm_rec())

    w = World(tmp, "stop_mismatch", candidates=False)
    w.arm()
    ex = w.ex()
    ex.cycle()
    w.fake.pos["KXFAKEA-26NOV25-T1"] = 7.0                    # a position Kalshi reports that no fill explains
    w.fake.cost["KXFAKEA-26NOV25-T1"] = 2.8
    for _ in range(3):
        w.clock.add(60)
        ex.cycle()
    check("f13. Kalshi's positions do not match the fills for 3 loops: stop + OFF (the P&L could not be trusted)",
          ex.done and "do not match" in w.arm_rec()["stopped"], w.arm_rec())

    w = World(tmp, "stop_silent", candidates=False)
    w.arm()
    ex = w.ex()
    ex.cycle()
    w.fake.down = True
    for _ in range(17):
        w.clock.add(60)
        ex.cycle()
    st = w.stops()
    check("f14. Kalshi silent for 15 minutes: stop + OFF; the push says it could NOT reach Kalshi and the orders expire by themselves "
          "within 20 minutes", ex.done and "15 minutes" in w.arm_rec()["stopped"] and st and "expires by itself" in st[0]["body"], st)

    w = World(tmp, "stop_env", candidates=False)
    w.arm()
    ex = w.ex(env=dict(w.env, LE_KALSHI_LIVE="0"))
    ex.cycle()
    check("f15. LE_KALSHI_LIVE=0 on a running loop: stop, OFF, nothing placed", ex.done and not w.fake.posts() and w.arm_rec()["armed"] is False)


# ================================================================================================ g. alerts
def part_alerts(tmp):
    w = World(tmp, "alerts", candidates=False, cash=500.0)
    w.arm()
    ex = w.ex()
    side = "bid"
    days = {}
    for i in range(360):                                    # 30 hours, a loop every 5 minutes, a fill almost every loop
        ex.cycle()
        if ex.done:
            break
        o = next((x for x in w.fake.ours() if x["ticker"] == "KXFAKEA-26NOV25-T2" and x["book_side"] == side), None)
        if o:
            w.fake.fill(o["order_id"], 1)
            side = "ask" if side == "bid" else "bid"
        w.clock.add(300)
    for p in w.pushes:
        days.setdefault(KL.et_day(p["t"]), []).append(p)
    per_day = {d: len(v) for d, v in days.items()}
    fills = {d: len([p for p in v if "fill" in p["title"]]) for d, v in days.items()}
    summ = [p for p in w.pushes if p["title"].startswith("Kalshi day ")]
    check("g1. a busy 30 hours (~360 fills): at most 10 pushes per ET day, fills batched (at most 6 fill pushes a day, an hour apart), "
          "exactly one day summary at the ET day change", not ex.done and all(v <= KL.PUSH_DAY_MAX for v in per_day.values())
          and all(v <= KL.FILL_PUSH_DAY_MAX for v in fills.values()) and len(summ) == 1 and sum(fills.values()) >= 6
          and ex.st["fills_today"] > 0, (per_day, fills, len(summ), ex.done))
    gaps = [b["t"] - a["t"] for a, b in zip([p for p in w.pushes if "fill" in p["title"]], [p for p in w.pushes if "fill" in p["title"]][1:])
            if KL.et_day(a["t"]) == KL.et_day(b["t"])]
    check("g2. fill pushes are at least an hour apart", all(g >= KL.FILL_PUSH_GAP_S for g in gaps), gaps)
    open(KL.paths(w.sd)["kill"], "w").write("kill")
    ex.cycle()
    check("g3. a stop still goes out at once when the day's budget is used", len(w.stops()) == 1 and w.stops()[0]["priority"] == "high", w.stops())
    text = json.dumps(w.pushes)
    check("g4. no key id, no key path, no PEM text in any push; every title ASCII and short", KEY_ID not in text and "PRIVATE" not in text
          and w.home not in text and all(p["title"].isascii() and len(p["title"]) <= 120 for p in w.pushes), [p["title"] for p in w.pushes][:5])
    first = next(p for p in w.pushes if "fill" in p["title"])
    check("g5. a fill push says it plainly: 'Kalshi: N fill(s) | day +$x', what was bought at what price, $ in use of the cap",
          re.match(r"Kalshi: \d+ fills? \| day [+-]?\$\d", first["title"]) and "Bought" in first["body"] and "In use" in first["body"], first)
    w2 = World(tmp, "alerts_none", candidates=False)
    w2.arm()
    ex2 = KL.Executor(w2.api(), state_dir=w2.sd, plan_path=w2.plan, cand_dir=w2.cands, env=w2.env, clock=w2.clock, poster=w2.poster, alert_cfg={})
    ex2.cycle()
    check("g6. no private alert topic on the PC: no push at all (never a public topic), the loop still runs", not w2.pushes and w2.fake.ours())


# ================================================================================================ h. dry run + the owner's files
def part_dry(tmp):
    w = World(tmp, "dry")
    api = KL.Api(http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0)
    lines = []
    real = KL.paths()["dir"]
    existed = os.path.exists(real)
    r = KL.dry_run(api=api, plan_path=w.plan, cand_dir=w.cands, now=w.clock(), say=lines.append)
    txt = "\n".join(lines)
    check("h1. the dry run (no key): public prices only, it prints the 6 quotes + the taker bet it WOULD place with $, and the total",
          len(r["orders"]) == 7 and txt.count("would rest") == 6 and txt.count("would take") == 1 and "buy YES" in txt and "nothing sent" in txt
          and "Total" in txt, txt)
    check("h2. ... zero writes, no signed call, no /portfolio call, no state file", r["api_writes"] == 0
          and not any(c[0] != "GET" or c[1].startswith("/portfolio") for c in w.fake.calls) and not os.path.exists(w.sd)
          and os.path.exists(real) == existed, [c[:2] for c in w.fake.calls if c[0] != "GET"])
    bats = {}
    for name in ("KALSHI_KEY_SETUP.bat", "KALSHI_LIVE.bat", "KALSHI_STOP.bat"):
        raw = open(os.path.join(ROOT, name), "rb").read()
        bats[name] = (b"\n" not in raw.replace(b"\r\n", b"") and raw.endswith(b"\r\n") and all(b < 128 for b in raw), raw.decode("ascii", "replace"))
    check("h3. the three .bat files: CRLF, ASCII", all(v[0] for v in bats.values()), {k: v[0] for k, v in bats.items()})
    live, stop, key = bats["KALSHI_LIVE.bat"][1], bats["KALSHI_STOP.bat"][1], bats["KALSHI_KEY_SETUP.bat"][1]
    code = lambda t: "\n".join(ln for ln in t.splitlines() if not ln.lower().startswith("rem"))  # noqa: E731
    check("h4. KALSHI_LIVE.bat runs --go (the owner types the phrase himself); no .bat passes a phrase, arms or names the key",
          "-m engine.kalshi_live --go" in live and not any(x in code(b) for b in (live, stop, key) for x in ("--phrase", "--arm", "ACCEPT", "KALSHI_KEY_ID", ".pem")),
          code(live))
    check("h5. KALSHI_STOP.bat asks Y first, then --stop; KALSHI_KEY_SETUP.bat runs scripts\\kalshi_key_setup.ps1 and pauses",
          "set /p" in stop and "--stop" in stop and re.search(r'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\\kalshi_key_setup\.ps1".*& pause', key))
    ps = open(os.path.join(ROOT, "scripts", "kalshi_key_setup.ps1"), encoding="ascii").read()
    lines_ = [ln for ln in ps.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    body = "\n".join(lines_[lines_.index("#>") + 1:] if "#>" in lines_ else lines_)
    printers = [ln for ln in body.splitlines()
                if re.search(r"(?i)\b(Write-Host|Write-Output|Stop-WithFix|echo)\b[^;{}]*\$(kid|sec|bstr|head|oldId)\b", re.sub(r"'[^']*'", "''", ln))]
    check("h6. the key setup: the Key ID read hidden (Read-Host -AsSecureString), never printed; the key file MOVED to "
          "OLYMPUS_HOME\\kalshi (outside the bot folder) and the folder locked to the user (icacls); the check is the read-only --check-key",
          "Read-Host -AsSecureString" in body and not printers and "Move-Item" in body and "Join-Path $Home1 'kalshi'" in body
          and "icacls" in body and "--check-key" in body and "kalshi_key.pem" in body, printers)
    check("h7. the key never on a command line (python reads the file itself), no PS7-only syntax, ASCII",
          not re.search(r"\$Python[^\n]*\$(kid|sec|head|KeyFile)", body) and not re.search(r"\?\?|\?\.|\s&&\s|\s\|\|\s|-AsPlainText", body), body[:200])


# ================================================================================================ i. card, phone, PC hook
def part_card(tmp, w_loop):
    off = os.path.join(tmp, "card_off")
    c = KL.read_card(now=T0, state_dir=off)
    check("i1. the public card when OFF: {kind, st: off}, tiny", c and c["st"] == "off" and len(json.dumps(c)) <= KL.CARD_MAX, c)
    c2 = KL.read_card(now=w_loop.clock(), state_dir=w_loop.sd)
    check("i2. while live: st live, today's $, fills, resting orders, cap and stop; <= 200 bytes; no ticker, no id",
          c2["st"] == "live" and {"net", "f", "o", "cap", "stop"} <= set(c2) and len(json.dumps(c2, separators=(",", ":"))) <= KL.CARD_MAX
          and "KX" not in json.dumps(c2), c2)
    c3 = KL.read_card(now=w_loop.clock() + 600, state_dir=w_loop.sd)
    check("i2b. armed but no loop on the PC for 10 min (a PC restart): the card says 'idle', never 'live'", c3["st"] == "idle"
          and KL.phone_view(state_dir=w_loop.sd, now=w_loop.clock() + 600).startswith("ARMED, but not running"), c3)
    said = KL.phone_press("pause", now=T0, state_dir=off)
    check("i3. a phone press while Kalshi is OFF does nothing and writes nothing", said == "" and not os.path.exists(off), said)
    from engine import phone_safety as PS

    class Rc:
        done_path = os.path.join(tmp, "remote_done.json")

        def run_cmd(self, c, d, now):
            return "done", "PAUSED until 4 PM ET"

        def _finish(self, *a, **k):
            pass

        def _hook(self, *a):
            pass
    old = KL.STATE_DIR
    try:
        KL.STATE_DIR = w_loop.sd
        r = PS.run(Rc(), "pause", {"confirm": "pause"}, now=w_loop.clock(), log_path=os.path.join(tmp, "ps_log.jsonl"))
        KL.STATE_DIR = off
        r2 = PS.run(Rc(), "pause", {"confirm": "pause"}, now=w_loop.clock(), log_path=os.path.join(tmp, "ps_log.jsonl"))
    finally:
        KL.STATE_DIR = old
    ctl = json.load(open(KL.paths(w_loop.sd)["control"], encoding="utf-8"))
    check("i4. a ZEUS Safety PAUSE press (engine/phone_safety.run) reaches Kalshi when it is ON ('Kalshi: paused' in the answer, a "
          "command queued) and adds nothing when it is OFF", "Kalshi: paused" in r["said"] and ctl["cmds"][-1]["cmd"] == "pause"
          and "Kalshi" not in r2["said"], (r, r2))
    ps_src = open(os.path.join(ROOT, "engine", "phone_safety.py"), encoding="utf-8").read()
    check("i5. phone_safety still never names 'armed' and its action list is unchanged (pause / resume / flatten / kill)",
          "armed" not in ps_src and set(PS.ACTIONS) == {"pause", "resume", "flatten", "kill"})
    spawned = []
    wm = World(tmp, "maybe", candidates=False)
    kw = {"say": lambda *_: None, "state_dir": wm.sd, "spawn_fn": lambda sd: spawned.append(sd) or 7, "plan_path": wm.plan, "cand_dir": wm.cands}
    r0 = KL.maybe_run(env=wm.env, now=wm.clock(), **kw)
    wm.arm()
    r1 = KL.maybe_run(env=wm.env, now=wm.clock(), **kw)
    KL.save_state(KL.paths(wm.sd), dict(KL.load_state(KL.paths(wm.sd)), t=wm.clock()))
    r2 = KL.maybe_run(env=wm.env, now=wm.clock() + 500, **kw)
    r3 = KL.maybe_run(env=wm.env, now=wm.clock() + 30, **kw)
    r4 = KL.maybe_run(env=dict(wm.env, LE_KALSHI_LIVE="0"), now=wm.clock() + 900, **kw)
    check("i6. the PC hook maybe_run: not armed = nothing; armed + no loop = start it once; a fresh loop or LE_KALSHI_LIVE=0 = nothing; "
          "never raises", r0 is None and r1 == 7 and r3 is None and r4 is None and len(spawned) == 2 and r2 == 7, (r0, r1, r2, r3, r4, spawned))


# ================================================================================================ j. wiring
def part_cli(tmp):
    """KALSHI_STOP.bat (--stop) when the loop is not running: it cancels everything itself with the key, OFF, kill switch."""
    w = World(tmp, "cli_stop", candidates=False)
    w.arm()
    w.ex().cycle()
    had = len(w.fake.ours())
    out = []
    old_api, old_post = KL.api_from_key, KL._default_poster
    try:
        KL.api_from_key = lambda env=None, **kw: w.api()
        KL._default_poster = lambda base, topic, msg: out.append(msg) or True
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = KL.main(["--stop", "--state-dir", w.sd])
        said = buf.getvalue()
    finally:
        KL.api_from_key, KL._default_poster = old_api, old_post
    check("i7. KALSHI_STOP.bat with no loop running: every resting order cancelled by the command itself, the kill switch file, OFF",
          rc == 0 and had == 6 and not w.fake.orders and os.path.exists(KL.paths(w.sd)["kill"]) and not KL.arm_state(state_dir=w.sd)[0]
          and "cancelled" in said, (rc, said, len(w.fake.orders)))
    fresh = os.path.join(tmp, "cli_never")
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = KL.main(["--stop", "--state-dir", fresh])
    check("i8. KALSHI_STOP.bat on a PC where Kalshi was never on: 'OFF already', nothing written", rc == 0 and "OFF already" in buf.getvalue()
          and not os.path.exists(fresh), buf.getvalue())


def part_wiring():
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import run_area
    check("j1. tests/run_area.py: the kalshi area runs this suite", "kalshi_live" in run_area.AREAS["kalshi"])
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("j2. data/kalshi_live/ (arm record, state, commands, log, card) is gitignored; *.pem too", "data/kalshi_live/" in gi and "*.pem" in gi)
    html = open(os.path.join(ROOT, "tools", "web_public", "kalshi", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "tools", "web_public", "kalshi", "kalshi.js"), encoding="utf-8").read()
    check("j3. the Kalshi page says plainly 'PAPER: the PC records every window with no money. Live only when you type the phrase' "
          "(night-kalshi8), shows the K8 status card, and reads the PC card (kalshi_live)",
          "PAPER: the PC records every window with no money. Live only when you type the phrase" in re.sub(r"<[^>]+>", "", html)
          and 'id="k8s"' in html and "kalshi_live_pub" in js and "function k8Show" in js, "")
    src = open(os.path.join(ROOT, "engine", "kalshi_live.py"), encoding="utf-8").read()
    check("j4. the executor never sends a market order or a v1 order call, and its only POST is /portfolio/events/orders",
          '"type": "market"' not in src and "'/portfolio/orders'" not in src and src.count('"POST"') == 2, "")


def main():
    tmp = tempfile.mkdtemp(prefix="kalshilive-")
    try:
        part_signing(tmp)
        part_plan(tmp)
        part_caps(tmp)
        part_arming(tmp)
        w = part_loop(tmp)
        part_stops(tmp)
        part_alerts(tmp)
        part_dry(tmp)
        part_card(tmp, w)
        part_cli(tmp)
        part_wiring()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
