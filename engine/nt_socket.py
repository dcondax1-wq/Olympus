"""NinjaTrader socket bridge adapter (PAPER PROTOTYPE, big-execution 2026-11-26).

Why: most live failures came from the FILE bridge, not from NinjaTrader's order routing: OIF files in a OneDrive-synced
Documents folder (sync filter locks, 600 file reads per poll), a watcher that can read an empty file, order files that must be
withdrawn when NinjaTrader is slow, outgoing\\ wiped on a restart (research/writeups/execution-2026-11-26.md).
MFFU accounts can only be traded through Tradovate-connected platforms (no Rithmic / CQG / ProjectX; Tradovate gives prop
accounts no API key), so NinjaTrader stays the route; this replaces only the TRANSPORT:

    bot (Python)  --TCP 127.0.0.1:36975, one JSON reply per line-->  ninjatrader/LE_Bridge.cs (an AddOn inside NinjaTrader)
                                                                      -> NinjaTrader's own Account API (Submit / Change /
                                                                         Cancel / Flatten) + Account.Orders / Positions

Everything above the transport is the tested NinjaTraderAdapter, unchanged (subclass): the same OIF command lines (built and
validated by engine/ninjatrader.py, so LE_Bridge speaks the documented OIF grammar), bracket logic, write-ahead state file,
caps, session gates, kill, allowlist, NinjaTrader-restart detection. What changes:
  * a command is acknowledged by NinjaTrader in the same call (no file to pick up / withdraw; nothing in Documents\\)
  * every command carries its send time + a TTL; LE_Bridge refuses an expired one, so an order can never run late
  * one snapshot per poll (orders, positions, connections, accounts) instead of hundreds of file reads
  * bridge unreachable = no entry, and tick() does nothing (no false "stop missing" flatten while blind); alert after 60 s

PAPER ONLY on this branch: any account that is not a NinjaTrader simulation account (Sim101 / SimNNN / PlaybackNNN) is refused
here AND in LE_Bridge.cs, whatever the start config says. Promoting it to live is a separate, owner-approved change.

Wire protocol (UTF-8, one request line -> one JSON line):
  PING                                          -> {"ok": true, "build": "...", "t": unix}
  OIF <req> <sent_ms> <ttl_ms> <line>|<line>..  -> {"ok": true, "id": req, "done": n} | {"ok": false, "id": req, "error": ...}
  SNAP <account>                                -> {"ok": true, "t": unix, "orders": {id: {"state", "filled", "avg", "t"}},
                                                    "positions": [{"instrument", "side", "qty", "avg", "t"}],
                                                    "connections": {name: "CONNECTED" | "DISCONNECTED"}, "accounts": [...]}

  python -m engine.nt_socket --selftest     offline: a simulated bridge on a local port (no NinjaTrader, no network)
  python -m engine.nt_socket --ping         is LE_Bridge answering on this PC?
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time

from . import ninjatrader as nt
from .ninjatrader import NinjaTraderAdapter, is_sim, parse_order_state, validate_line

HOST = "127.0.0.1"
PORT = 36975                       # LE_Bridge default (NinjaTrader's own ATI socket is 36973; never that)
PORT_ENV = "LE_BRIDGE_PORT"
SNAP_TTL = 0.15                    # one snapshot serves every read of one poll
DOWN_ALERT_S = 60.0
PAPER_ONLY = True                  # this branch: simulation accounts only (also hard-coded in LE_Bridge.cs)


class BridgeClient:
    """One persistent TCP connection to LE_Bridge with reconnect + backoff. request() never raises: None = no answer."""

    def __init__(self, host=HOST, port=None, timeout=2.0):
        self.host, self.port = host, int(port or os.environ.get(PORT_ENV) or PORT)
        self.timeout = timeout
        self.sock = None
        self.buf = b""
        self.lock = threading.Lock()
        self.next_try = 0.0
        self.fails = 0
        self.down_since = None
        self.last_rtt_ms = None
        self.rtts: list = []           # every round trip (ms), for the side-by-side comparison

    def _connect(self) -> bool:
        if self.sock is not None:
            return True
        now = time.time()
        if now < self.next_try:
            return False
        try:
            s = socket.create_connection((self.host, self.port), timeout=self.timeout)
            s.settimeout(self.timeout)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock, self.buf, self.fails = s, b"", 0
            return True
        except OSError:
            self.fails += 1
            self.next_try = now + min(5.0, 0.25 * 2 ** min(self.fails, 5))     # 0.5 s .. 5 s
            if self.down_since is None:
                self.down_since = now
            return False

    def close(self):
        try:
            if self.sock is not None:
                self.sock.close()
        except OSError:
            pass
        self.sock, self.buf = None, b""

    def request(self, line: str, sent_ok=None):
        """One request; a read-only request (PING / SNAP) that failed on an old connection is retried once on a new one
        (NinjaTrader restarted since the last poll). An OIF is never re-sent here: its outcome is read from the snapshot."""
        had = self.sock is not None
        out = self._request(line, sent_ok)
        if out is None and had and sent_ok is None and not line.startswith("OIF"):
            out = self._request(line, None)
        return out

    def _request(self, line: str, sent_ok=None):
        """Send one line, read one JSON line. sent_ok (a list) gets True appended once the bytes left this process: the
        caller can tell "never sent" (safe: not executed) from "sent, no answer" (unknown: verify via the snapshot)."""
        with self.lock:
            if not self._connect():
                return None
            t0 = time.perf_counter()
            try:
                self.sock.sendall(line.encode("utf-8") + b"\n")
                if sent_ok is not None:
                    sent_ok.append(True)
                while b"\n" not in self.buf:
                    chunk = self.sock.recv(65536)
                    if not chunk:
                        raise OSError("bridge closed the connection")
                    self.buf += chunk
                raw, self.buf = self.buf.split(b"\n", 1)
                out = json.loads(raw.decode("utf-8"))
            except (OSError, ValueError):
                self.close()
                if self.down_since is None:
                    self.down_since = time.time()
                return None
            self.last_rtt_ms = (time.perf_counter() - t0) * 1000.0
            self.rtts.append(self.last_rtt_ms)
            del self.rtts[:-5000]
            self.down_since = None
            return out


class NtSocketAdapter(NinjaTraderAdapter):
    name = "ninjatrader"               # the same adapter to the rest of the bot (ledgers, checks); only the transport differs
    transport = "socket"

    def __init__(self, cfg: dict | None = None, readonly: bool = False, clock=None, client: BridgeClient | None = None):  # noqa: D401
        cfg = dict(cfg or {})
        self.client = client or BridgeClient(cfg.get("bridge_host") or HOST, cfg.get("bridge_port"),
                                             float(cfg.get("bridge_timeout_s", 2.0)))
        self._snap_cache = None             # (monotonic time, snapshot)
        self._req = 0
        self._down_alerted = False
        self.bridge_ttl_ms = int(float(cfg.get("bridge_ttl_s", cfg.get("nt_ack_wait_s", 4.0))) * 1000)
        super().__init__(cfg, readonly=readonly, clock=clock)
        self.write_mode = "socket"

    # ------------------------------------------------------------------ gates
    def _live_gate(self):
        base = super()._live_gate()
        if base:
            return base
        if PAPER_ONLY and not is_sim(self.account):
            return (f"account {self.account} refused: the socket bridge is a PAPER prototype (Sim101 / SimNNN only) until the "
                    "owner approves it for live")
        return None

    def _gate(self, kind: str):
        g = super()._gate(kind)
        if g or kind != "entry":
            return g
        self._snap_cache = None
        if self._snapshot() is None:
            return {"ok": False, "error": "REFUSED: the NinjaTrader bridge (LE_Bridge add-on) is not answering"}
        return None

    # ------------------------------------------------------------------ transport: write
    def _sweep_stale_oifs(self, max_age: float):
        return None                          # nothing is ever left lying in a folder

    def _sweep_outbox(self, max_age: float):
        return None

    def _withdraw(self, path) -> bool:
        return False

    def folder_status(self) -> dict:
        up = self._snapshot() is not None
        return {"folder": self.folder, "bridge": f"{self.client.host}:{self.client.port}", "exists": os.path.isdir(self.folder),
                "incoming": up, "outgoing": up}

    def _write_oif(self, lines: list, label: str) -> dict:
        if self.readonly:
            return {"ok": False, "error": "REFUSED: read-only adapter"}
        for ln in lines:
            bad = validate_line(ln) or self._scope_problem(ln)
            if bad or "|" in ln:
                msg = f"internal: refused to send invalid OIF line {ln!r}: {'; '.join(bad) or 'contains |'}"
                self.last_error = msg
                self._log("error", msg)
                return {"ok": False, "error": msg}
        # a PING first on the same connection: a half-open socket (NinjaTrader closed, add-on restarted) is found by a
        # harmless request, so an order line is only sent on a connection that answered a moment ago
        if self.client.request("PING") is None and self.client.request("PING") is None:
            msg = "the NinjaTrader bridge (LE_Bridge) is not answering: nothing was sent"
            self.last_error = msg
            self._log("error", "NinjaTrader " + msg)
            return {"ok": False, "error": msg}
        self._req += 1
        self._seq += 1
        req = f"{self.file_tag or 'le'}{self._seq}"
        sent = []
        r = self.client.request(f"OIF {req} {int(time.time() * 1000)} {self.bridge_ttl_ms} " + "|".join(lines), sent_ok=sent)
        self._snap_cache = None
        name = f"socket#{req}"
        if r is None and not sent:
            msg = "the NinjaTrader bridge (LE_Bridge) is not answering: nothing was sent"
            self.last_error = msg
            self._log("error", "NinjaTrader " + msg)
            return {"ok": False, "error": msg}                          # never reached NinjaTrader: nothing to watch
        self._audit(name, lines)
        self._note_msgs(lines)
        if r is None:
            # sent, no answer: NinjaTrader may or may not have run it (the TTL caps how late). Like a file NinjaTrader took at
            # the last moment: the caller reads the snapshot to find out
            self._log("warn", f"NinjaTrader {label} -> {name}: sent, no answer from the bridge (checking the orders)")
            return {"ok": True, "file": name, "path": None, "lines": list(lines), "picked_up": True, "late": True}
        if not r.get("ok"):
            msg = f"the NinjaTrader bridge refused {label}: {r.get('error')}"
            self.last_error = msg
            self._log("error", "NinjaTrader " + msg)
            return {"ok": False, "error": msg, "file": name}
        self._log("broker", f"NinjaTrader {label} -> {name} ({self.client.last_rtt_ms or 0:.1f} ms): " + " | ".join(lines))
        return {"ok": True, "file": name, "path": None, "lines": list(lines), "picked_up": True,
                "rtt_ms": self.client.last_rtt_ms}

    def _send_lines(self, lines: list, label: str) -> dict:
        t0 = self.clock()
        r = self._write_oif(lines, label)
        if r.get("ok"):                                  # latency log: sent and acknowledged in the same request
            r.update(written_at=t0, picked_at=self.clock())
        return r

    # ------------------------------------------------------------------ transport: read
    def _snapshot(self):
        c = self._snap_cache
        if c is not None and time.monotonic() - c[0] < SNAP_TTL:
            return c[1]
        r = self.client.request(f"SNAP {self.account}")
        if not r or not r.get("ok"):
            self._snap_cache = None
            return None
        self._snap_cache = (time.monotonic(), r)
        return r

    def _wait(self, cond, timeout, step=0.05) -> bool:
        def fresh():
            self._snap_cache = None
            return cond()
        return super()._wait(fresh, timeout, step)

    def read_order(self, order_id: str, listing: list | None = None):
        s = self._snapshot()
        o = (s or {}).get("orders", {}).get(order_id)
        if not o:
            return None
        st = parse_order_state(f"{o.get('state', '')};{int(o.get('filled') or 0)};{float(o.get('avg') or 0)}")
        if st is None:
            self._unparsable(order_id, json.dumps(o))
            return None
        st["mtime"] = o.get("t")
        return st

    def _pos_name(self, inst):
        return f"{inst}_{self.account}_Position.txt"

    def positions(self) -> dict:
        s = self._snapshot()
        out = []
        for p in (s or {}).get("positions", []):
            side = str(p.get("side", "")).upper()
            if side not in ("LONG", "SHORT", "FLAT"):
                continue
            out.append({"instrument": p.get("instrument"), "side": side, "qty": int(p.get("qty") or 0),
                        "avg": float(p.get("avg") or 0), "file": self._pos_name(p.get("instrument")), "mtime": p.get("t")})
        return {"ok": s is not None, "account": self.account, "positions": out}

    def _listing(self) -> list:
        s = self._snapshot()
        if s is None:
            return []
        return ([f"{oid}.txt" for oid in s.get("orders", {})] + [self._pos_name(p.get("instrument")) for p in s.get("positions", [])]
                + [f"{c}.txt" for c in s.get("connections", {})])

    def connections(self) -> dict:
        s = self._snapshot()
        return {str(k): str(v).upper() for k, v in ((s or {}).get("connections") or {}).items()}

    def _all_disconnected(self, conn: dict) -> bool:
        if not (conn and all(v == "DISCONNECTED" for v in conn.values())):
            return False
        s = self._snapshot() or {}
        return nt.SIM_ACCOUNT.match(str(self.account or "")) is not None or str(self.account) not in (s.get("accounts") or [])

    # ------------------------------------------------------------------ the poll
    def tick(self) -> dict:
        if self.disabled or self.readonly:
            return super().tick()
        self._snap_cache = None                           # every poll starts from a fresh snapshot
        if self._snapshot() is None:
            down = self.client.down_since or time.time()
            if time.time() - down >= DOWN_ALERT_S and not self._down_alerted and any(
                    lg["status"] in nt.OPEN_STATUSES for lg in self.legs):
                self._down_alerted = True
                self._alert(f"NinjaTrader bridge not answering for {time.time() - down:.0f}s with a trade open on {self.account}: "
                            "the broker's stop is still working, but check NinjaTrader now (is it running, LE_Bridge enabled?)")
            return {"ok": True, "idle": "bridge not answering", "legs": len(self.legs)}
        self._down_alerted = False
        return super().tick()

    def status(self) -> dict:
        st = super().status()
        rt = sorted(self.client.rtts)
        st["bridge"] = {"host": self.client.host, "port": self.client.port, "up": self._snapshot() is not None,
                        "down_since": self.client.down_since, "rtt_ms_p50": rt[len(rt) // 2] if rt else None,
                        "rtt_ms_p99": rt[int(len(rt) * 0.99)] if rt else None, "paper_only": PAPER_ONLY}
        return st


TRANSPORT_ENV = "LE_NT_TRANSPORT"


def make_adapter(cfg: dict | None = None, **kw):
    """engine/live.ADAPTERS["ninjatrader"]: the FILE bridge (NinjaTraderAdapter, today) unless the transport is switched to
    "socket" (start / account cfg {"nt_transport": "socket"} or env LE_NT_TRANSPORT=socket; default OFF) AND the account is a
    NinjaTrader simulation account. While PAPER_ONLY a live account always keeps the file bridge, so the switch can never
    disable a live account."""
    c = cfg or {}
    want = str(c.get("nt_transport") or os.environ.get(TRANSPORT_ENV, "") or "file").strip().lower() == "socket"
    sim = False
    if want:
        try:                                             # red team 2026-11-26: an account lookup error never stops the bot from
            sim = bool(is_sim(nt.resolve_account(c)))    # starting: it means "not proven Sim" = the file bridge, as today
        except Exception:  # noqa: BLE001
            sim = False
    if want and sim:                                     # red team: Sim ONLY, whatever PAPER_ONLY says (a live account never
        return NtSocketAdapter(c, **kw)                  # changes transport through this switch)
    return NinjaTraderAdapter(c, **kw)


# ---------------------------------------------------------------------- a simulated LE_Bridge (self-test, exec_compare --fake)
class FakeBridge:
    """Plays LE_Bridge.cs on a local port: the same protocol, backed by ninjatrader._FakeNT's tested order simulation (its
    folder files are a by-product in a temp dir; the adapter never reads them). Knobs: .down (refuse connections),
    .mute (take OIF, answer nothing), .restart() (NinjaTrader restart: orders/positions forgotten, like a wiped outgoing)."""

    def __init__(self, folder, clock=time.time, port=0, sim_only=True):
        self.nt = nt._FakeNT(folder)
        self.clock = clock
        self.sim_only = sim_only
        self.t: dict = {}                    # order id / (acct, inst) -> last change time
        self.down = False
        self.mute = False
        self.requests: list = []
        self.lock = threading.Lock()
        orig_state, orig_pos = self.nt._state, self.nt._write_pos

        def _state(oid, o):
            self.t[oid] = self.clock()
            orig_state(oid, o)

        def _pos(acct, inst):
            self.t[(acct, inst)] = self.clock()
            orig_pos(acct, inst)
        self.nt._state, self.nt._write_pos = _state, _pos
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind((HOST, port))
        self.srv.listen(8)
        self.port = self.srv.getsockname()[1]
        self.conns: list = []
        self.alive = True
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.alive:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            if self.down:
                c.close()
                continue
            self.conns.append(c)
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def _serve(self, c):
        buf = b""
        try:
            while self.alive:
                chunk = c.recv(65536)
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    ln, buf = buf.split(b"\n", 1)
                    if self.down:
                        c.close()
                        return
                    out = self.handle(ln.decode("utf-8").strip())
                    if out is not None:
                        c.sendall((json.dumps(out) + "\n").encode("utf-8"))
        except OSError:
            return

    def handle(self, line: str):
        with self.lock:
            self.requests.append(line)
            parts = line.split(" ", 4)
            cmd = parts[0]
            if cmd == "PING":
                return {"ok": True, "build": "fake", "t": self.clock()}
            if cmd == "SNAP":
                acct = parts[1] if len(parts) > 1 else ""
                orders = {oid: {"state": o["state"], "filled": o["filled"], "avg": o["avg"] or 0, "t": self.t.get(oid)}
                          for oid, o in self.nt.orders.items() if o["account"] == acct}
                pos = []
                for (a, inst), (q, avg) in self.nt.pos.items():
                    if a == acct:
                        pos.append({"instrument": f"{inst} {self.nt.exchange}", "side": "LONG" if q > 0 else "SHORT" if q < 0 else "FLAT",
                                    "qty": abs(q), "avg": avg if q else 0, "t": self.t.get((a, inst))})
                return {"ok": True, "t": self.clock(), "orders": orders, "positions": pos,
                        "connections": {"Tradovate": "CONNECTED"}, "accounts": sorted({a for a, _ in self.nt.pos} | {acct})}
            if cmd == "OIF" and len(parts) == 5:
                req, sent_ms, ttl_ms, body = parts[1], int(parts[2]), int(parts[3]), parts[4]
                if time.time() * 1000 - sent_ms > ttl_ms:
                    return {"ok": False, "id": req, "error": f"expired ({time.time() * 1000 - sent_ms:.0f} ms > {ttl_ms} ms)"}
                lines = body.split("|")
                for ln in lines:
                    f = ln.split(";")
                    if self.sim_only and f[0] in ("PLACE", "CLOSEPOSITION", "REVERSEPOSITION") and not is_sim(f[1]):
                        return {"ok": False, "id": req, "error": f"bridge is paper-only: account {f[1]} refused"}
                    bad = validate_line(ln)
                    if bad:
                        return {"ok": False, "id": req, "error": "; ".join(bad)}
                self.nt.files.append((f"socket#{req}", lines))
                for ln in lines:
                    self.nt._do(ln)
                if self.mute:
                    return None
                return {"ok": True, "id": req, "done": len(lines)}
            return {"ok": False, "error": f"unknown command {cmd!r}"}

    def restart(self):
        with self.lock:
            self.nt.orders.clear()
            self.nt.pos.clear()
            self.t.clear()
        self.drop()

    def drop(self):
        for c in self.conns:
            try:
                c.shutdown(socket.SHUT_RDWR)
                c.close()
            except OSError:
                pass
        self.conns = []

    def close(self):
        self.alive = False
        self.drop()
        try:
            self.srv.close()
        except OSError:
            pass


def selftest(verbose=True) -> bool:
    import datetime as dt
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="le_ntsock_")
    saved = {k: os.environ.get(k) for k in (nt.LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER", nt.ALLOW_ENV, TRANSPORT_ENV)}
    for k in saved:
        os.environ.pop(k, None)
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond)))
        if verbose:
            print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not cond else ""))

    now = [dt.datetime(2026, 10, 21, 10, 5, tzinfo=nt.ET).timestamp()]       # a Wednesday 10:05 ET
    fb = FakeBridge(os.path.join(tmp, "fake_nt"), clock=lambda: now[0])
    folder = os.path.join(tmp, "NinjaTrader 8")
    os.makedirs(folder)
    alerts = []

    def make(extra=None):
        cfg = {"adapter": "nt-socket", "sym": "NQ", "armed": True, "nt_folder": folder, "params": {"max_micros": 40, "flat_mod": 955},
               "nt_max_entries_day": 999, "nt_state_path": os.path.join(tmp, "st.json"), "nt_audit_log": os.path.join(tmp, "a.log"),
               "bridge_port": fb.port, "bridge_timeout_s": 0.5, "nt_lock": False, **(extra or {})}
        ad = NtSocketAdapter(cfg, clock=lambda: now[0])
        ad._sleep = lambda s: now.__setitem__(0, now[0] + s)
        ad._alert_fn = alerts.append
        return ad

    try:
        if verbose:
            print("NinjaTrader socket bridge (paper prototype) offline self-test")
        ad = make()
        check("Sim101 enabled, bridge answering", not ad.disabled and ad.folder_status()["incoming"], str(ad.disabled))
        T = int(dt.datetime(2026, 10, 21, 10, 0, tzinfo=nt.ET).timestamp())
        k = len(fb.nt.files)
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 24990.13, "target": 25080.0, "entry": 25020.0, "entry_t": T})
        lg = ad.legs[0] if ad.legs else {}
        got = [ls for _, ls in fb.nt.files[k:]]
        exp = [[f"PLACE;Sim101;MNQ 12-26;BUY;2;MARKET;0;0;DAY;;{lg.get('entry_id')};;"],
               [f"PLACE;Sim101;MNQ 12-26;SELL;2;STOPMARKET;0;24990.25;DAY;{lg.get('oco')};{lg.get('stop_id')};;",
                f"PLACE;Sim101;MNQ 12-26;SELL;2;LIMIT;25080.00;0;DAY;{lg.get('oco')};{lg.get('target_id')};;"]]
        check("bracket: same OIF lines as the file adapter (entry, then the OCO stop + target), leg protected",
              r.get("ok") and got == exp and lg.get("status") == "protected", json.dumps([r, got]))
        p = ad.position_for("MNQ 12-26")
        check("snapshot: LONG 2 MNQ, stop + target WORKING", p and p["side"] == "LONG" and p["qty"] == 2
              and ad.read_order(lg["stop_id"])["state"] == "WORKING" and ad.read_order(lg["target_id"])["state"] == "WORKING")
        check("no files: nothing written in the NinjaTrader folder (no incoming / le_outbox)",
              not os.path.exists(os.path.join(folder, "incoming")) and not os.path.exists(os.path.join(folder, "le_outbox")))
        check("latency log: send_at / ack_at / fill_seen_at kept on the leg", all(lg.get(k) is not None for k in
                                                                                  ("send_at", "ack_at", "fill_seen_at")), str(lg))
        check("one position at a time", "still open" in ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990,
                                                                  "target": 25080, "entry": 25020}).get("error", ""))
        r = ad.send({"side": "modify", "stop": 25020.25, "entry_t": T})
        check("breakeven: CHANGE the stop", r.get("ok") and fb.nt.orders[lg["stop_id"]]["stop"] == 25020.25, json.dumps(r))
        ad2 = make()
        check("restart of the bot: bracket restored from the state file", len(ad2.legs) == 1 and ad2.legs[0]["stop_id"] == lg["stop_id"])
        r = ad2.send({"sym": "NQ", "side": "exit", "qty": 2, "reason": "TIME STOP", "entry_t": T})
        p = ad2.position_for("MNQ 12-26")
        check("exit: flat confirmed, stop + target cancelled", r.get("ok") and p and p["side"] == "FLAT"
              and fb.nt.orders[lg["stop_id"]]["state"] == "CANCELLED", json.dumps(r))
        ad = ad2
        # bridge down: entry refused, nothing sent; tick idles (no false flatten while blind)
        fb.down = True
        fb.drop()
        ad.client.next_try = 0
        n_req = len(fb.requests)
        r = ad.send({"sym": "NQ", "side": "sell", "qty": 1, "stop": 25050, "target": 24950, "entry": 25020, "entry_t": T + 600})
        check("bridge down: entry REFUSED, no command reached NinjaTrader", not r.get("ok") and "not answering" in r.get("error", "")
              and len(fb.requests) == n_req, json.dumps(r))
        check("bridge down: tick() idles", ad.tick().get("idle") == "bridge not answering")
        fb.down = False
        ad.client.next_try = 0
        time.sleep(0.05)
        r = ad.send({"sym": "NQ", "side": "sell", "qty": 1, "stop": 25050, "target": 24950, "entry": 25020, "entry_t": T + 900})
        check("bridge back: reconnects by itself, the next entry goes through", r.get("ok"), json.dumps(r))
        ad.tick()                                         # the bot's poll sees the protected trade's reports
        # protected trade, then the bridge restarts with NinjaTrader (snapshot wiped) -> reset guard blocks entries
        fb.restart()
        ad.client.next_try = 0
        time.sleep(0.05)
        ad.tick()
        check("NinjaTrader restart (orders / positions gone from the snapshot): entries blocked, owner alerted",
              ad.nt_reset is not None and "REFUSED" in ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990,
                                                                "target": 25080, "entry": 25020}).get("error", ""), str(ad.nt_reset))
        # TTL: a command older than its TTL is refused by the bridge (never runs late)
        out = fb.handle(f"OIF x1 {int(time.time() * 1000) - 9000} 4000 PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LEX1;;")
        check("TTL: an expired command is refused by the bridge", out and not out["ok"] and "expired" in out["error"], str(out))
        # paper only: a non-Sim account is refused by the adapter (even fully armed + allowlisted) AND by the bridge
        os.environ[nt.LIVE_ENV] = "1"
        os.environ[nt.ALLOW_ENV] = "MFFUEVAL123"
        live = make({"account": "MFFUEVAL123", "nt_account": "MFFUEVAL123", "confirm": nt.LIVE_PHRASE,
                     "nt_state_path": os.path.join(tmp, "st_live.json")})
        out = fb.handle(f"OIF x2 {int(time.time() * 1000)} 4000 PLACE;MFFUEVAL123;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LEX2;;")
        check("paper only: an armed, allowlisted MFFU account is refused by the adapter and by the bridge",
              live.account != "Sim101" and live.disabled and "PAPER" in live.disabled and not out["ok"], f"{live.account}: {live.disabled}")
        os.environ.pop(nt.LIVE_ENV, None)
        os.environ.pop(nt.ALLOW_ENV, None)
        # kill: account scope closes this account only
        k = len(fb.nt.files)
        ad3 = make({"nt_state_path": os.path.join(tmp, "st3.json")})
        ad3.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990, "target": 25080, "entry": 25020, "entry_t": T + 1200})
        r = ad3.kill()
        lines = [ln for _, ls in fb.nt.files[k:] for ln in ls]
        check("kill (account): CLOSEPOSITION on Sim101 only, never FLATTENEVERYTHING, flat after",
              r.get("ok") and any(ln.startswith("CLOSEPOSITION;Sim101;") for ln in lines)
              and not any(ln.startswith("FLATTENEVERYTHING") for ln in lines)
              and ad3.position_for("MNQ 12-26")["side"] == "FLAT", json.dumps(r))
        check("kill: no entry after it", "kill switch" in ad3.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990,
                                                                     "target": 25080, "entry": 25020}).get("error", ""))
        # the opt-in transport (engine/live.ADAPTERS["ninjatrader"] = make_adapter): OFF by default; socket only for a Sim account
        base = {"adapter": "ninjatrader", "nt_folder": folder, "nt_lock": False, "nt_state_path": os.path.join(tmp, "st_f.json"),
                "bridge_port": fb.port}
        f0 = make_adapter(base)
        f1 = make_adapter({**base, "nt_transport": "socket"})
        f2 = make_adapter({**base, "nt_transport": "socket", "account": "MFFUEVAL123", "nt_account": "MFFUEVAL123"})
        os.environ[TRANSPORT_ENV] = "socket"
        f3 = make_adapter(base)
        os.environ.pop(TRANSPORT_ENV, None)
        check("transport switch: default = file bridge; socket only when switched on AND a Sim account; a live account keeps files",
              type(f0) is NinjaTraderAdapter and type(f1) is NtSocketAdapter and type(f2) is NinjaTraderAdapter
              and type(f3) is NtSocketAdapter and f1.name == "ninjatrader", f"{type(f0)} {type(f1)} {type(f2)} {type(f3)}")
        from engine import live as _live, nt_socket as _me      # the imported module (this file may run as __main__)
        check("engine/live.ADAPTERS['ninjatrader'] is the factory", _live.ADAPTERS["ninjatrader"] is _me.make_adapter)
        rt = sorted(ad3.client.rtts)
        check("latency recorded (local round trip)", rt and rt[len(rt) // 2] < 50, f"p50 {rt[len(rt) // 2] if rt else None}")
    finally:
        fb.close()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c in checks)
    if verbose:
        print(f"{sum(c for _, c in checks)}/{len(checks)} checks passed")
    return ok


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        return 0 if selftest() else 1
    if "--ping" in argv:
        c = BridgeClient()
        r = c.request("PING")
        print(json.dumps(r) if r else f"LE_Bridge not answering on {c.host}:{c.port}")
        return 0 if r else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
