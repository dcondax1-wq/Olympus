"""Data feed over ntfy (night-data 2026-11-18, engine/datafeed.py + tools/data_pull.py --latest + the datapipe's git switch).

Offline: a local fake ntfy server (127.0.0.1, the same JSON / attachment API as ntfy.sh, its 2 MB limit and 3 h expiry) stands
in for ntfy.sh; a fake clock drives the cloud's wait and the PC's 5-minute ticks; the PC and the cloud data folders are temp
fixtures (MNQ + MES NinjaTrader feed files, ledgers with real-looking account ids, TradingView-like data/*.csv).

  python -X utf8 -m tests.test_datafeed        # ~20 s
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import datafeed as DF, datapipe as DP  # noqa: E402
from tools import data_pull as PULL  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
ACCT_A, ACCT_B = "MFFUEVB50K000001234", "MFFUEVB25K000009999"
DEAD_PID = 2 ** 22 + 12345                     # above Linux pid_max: never a live process
DAYS = ("2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19")


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:500]}"))


def ts(day, hh, mm=0):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), ET).timestamp())


def wjson(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


# ================================================================================================ fake ntfy.sh
class FakeNtfy:
    """The ntfy.sh API this code uses: POST/PUT /<topic> (Filename -> attachment, Message header), GET /<topic>/json?poll=1&since=,
    GET /file/<id>.bin. Attachments over 2 MB -> 413; expire 3 h after the (fake) clock."""

    def __init__(self):
        self.msgs, self.files, self.calls = {}, {}, []
        self.clock = lambda: 0
        self.fail_put = None
        self.tamper = False
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json"):
                b = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                fake.calls.append(("GET", self.path))
                u = urllib.parse.urlparse(self.path)
                if u.path.startswith("/file/"):
                    fid = u.path[len("/file/"):].split(".")[0]
                    m = fake.files.get(fid)
                    if m is None or m[1] < fake.clock():
                        return self._send(404, '{"code":40401,"http":404,"error":"not found"}')
                    return self._send(200, (m[0] + b"x") if fake.tamper else m[0], "application/octet-stream")
                parts = u.path.strip("/").split("/")
                if len(parts) == 2 and parts[1] == "json":
                    since = (urllib.parse.parse_qs(u.query).get("since") or ["all"])[0]
                    lo = fake.since(since)
                    rows = [m for m in fake.msgs.get(parts[0], []) if m["time"] >= lo and m["expires"] > fake.clock()]
                    return self._send(200, "".join(json.dumps(m) + "\n" for m in rows), "application/x-ndjson")
                return self._send(404, "{}")

            def do_PUT(self):
                self._pub("PUT")

            def do_POST(self):
                self._pub("POST")

            def _pub(self, method):
                fake.calls.append((method, self.path))
                topic = urllib.parse.urlparse(self.path).path.strip("/")
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if method == "PUT" and fake.fail_put:
                    return self._send(fake.fail_put, json.dumps({"code": fake.fail_put * 100, "http": fake.fail_put}))
                now = int(fake.clock())
                mid = secrets.token_hex(6)
                m = {"id": mid, "time": now, "expires": now + 43200, "event": "message", "topic": topic}
                fname = self.headers.get("Filename") or self.headers.get("X-Filename")
                if fname or len(body) > 4096:
                    if len(body) > 2 * 1024 * 1024:
                        return self._send(413, '{"code":41301,"http":413,"error":"attachment too large"}')
                    fake.files[mid] = (body, now + 10800)
                    m["message"] = self.headers.get("Message") or f"You received a file: {fname}"
                    m["attachment"] = {"name": fname, "type": "application/octet-stream", "size": len(body),
                                       "expires": now + 10800, "url": f"{fake.base}/file/{mid}.bin"}
                else:
                    m["message"] = self.headers.get("Message") or body.decode("utf-8", "replace")
                fake.msgs.setdefault(topic, []).append(m)
                self._send(200, json.dumps(m))

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def since(self, s):
        if s == "all":
            return 0
        if re.fullmatch(r"\d+", s):
            return int(s)
        m = re.fullmatch(r"(\d+)([smh])", s)
        return self.clock() - int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)] if m else 0

    def n(self, method, topic=None):
        return sum(1 for mth, p in self.calls if mth == method and (topic is None or p.startswith(f"/{topic}")))

    def post(self, topic, body: dict, t=None):
        now = int(t if t is not None else self.clock())
        m = {"id": secrets.token_hex(6), "time": now, "expires": now + 43200, "event": "message", "topic": topic,
             "message": json.dumps(body)}
        self.msgs.setdefault(topic, []).append(m)
        return m


class Clock:
    def __init__(self, t):
        self.t = float(t)

    def time(self):
        return self.t


# ================================================================================================ fixtures
def price(t, base):
    x = (t - 1790000000) / 60.0
    return round((base + 0.002 * x + 12.0 * __import__("math").sin(x / 37.0)) * 4) / 4


def session_minutes(day, upto=None):
    """Bar open times of one CME day: 18:00 ET the evening before -> 16:59 ET (the 17:00 halt), Monday = from Sunday 18:00."""
    d = dt.date.fromisoformat(day)
    prev = d - dt.timedelta(days=3 if d.weekday() == 0 else 1)
    t0 = int(dt.datetime.combine(prev, dt.time(18, 0), ET).timestamp())
    t1 = ts(day, 17, 0)
    return [t for t in range(t0, t1, 60) if upto is None or t < upto]


def bars_1m(days, base, upto=None):
    rows = []
    for day in days:
        for t in session_minutes(day, upto):
            p = price(t, base)
            rows.append((t, p, p + 1.0, p - 0.75, p + 0.25, 100 + (t // 60) % 50))
    return rows


def agg5(rows):
    b5 = {}
    for t, o, h, lo, c, v in rows:
        k = t // 300 * 300
        x = b5.get(k)
        b5[k] = [k, o, h, lo, c, v] if x is None else [k, x[1], max(x[2], h), min(x[3], lo), c, x[5] + v]
    return [tuple(r) for r in sorted(b5.values())]


def make_pc(tmp, now):
    """A PC: NinjaTrader le_feed MNQ + MES 1m/5m (Nov 12 .. now: the Nov 19 session has started), ledgers, a nightly review."""
    root, nt = os.path.join(tmp, "pc"), os.path.join(tmp, "nt")
    fd = os.path.join(nt, "le_feed")
    os.makedirs(fd, exist_ok=True)
    for sym, base in (("MNQ", 21000.0), ("MES", 6000.0)):
        r1 = bars_1m(DAYS, base, upto=now - 60)
        for tf, rows in (("1m", r1), ("5m", agg5(r1)[:-1])):
            with open(os.path.join(fd, f"{sym}_{tf}.csv"), "w") as fh:
                fh.write("".join(",".join(str(x) for x in r) + "\n" for r in rows))
        with open(os.path.join(fd, f"{sym}_instrument.txt"), "w") as fh:
            fh.write(f"{sym} 12-26\n")
    with open(os.path.join(fd, "accounts.csv"), "w") as fh:
        fh.write(f"{ACCT_A},Connected\n{ACCT_B},Connected\nSim101,Connected\n")
    e1 = ts("2026-11-17", 9, 45)
    wjson(os.path.join(root, "data", "live_state.json"), {"adapter": "ninjatrader", "nt_account": ACCT_A, "balance": 49192.78, "ledger": [
        {"t": e1 + 5, "side": "buy", "qty": 3, "entry_t": e1, "entry": 21003.0, "stop": 20990.0, "target": 21030.0,
         "result": {"ok": True, "adapter": "ninjatrader", "account": ACCT_A,
                    "path": "C:\\Users\\owner\\Documents\\NinjaTrader 8\\incoming\\oif1.txt", "lines": [f"PLACE;{ACCT_A};MNQ 12-26;BUY;3"]}},
        {"t": e1 + 900, "side": "exit", "qty": 3, "entry_t": e1, "reason": "TARGET", "pnl": 156.3, "exit_t": e1 + 900,
         "result": {"ok": True, "adapter": "ninjatrader", "account": ACCT_A}}]})
    wjson(os.path.join(root, "data", "live_state_accounts.json"), {"accounts": {"b25k_2": {"nt_account": ACCT_B, "ledger": [
        {"t": e1 + 6, "side": "buy", "qty": 1, "entry_t": e1, "result": {"ok": False, "adapter": "ninjatrader",
                                                                        "error": f"order refused for {ACCT_B}: Limit 0"}}]}}})
    e2 = ts("2026-11-18", 10, 0)
    wjson(os.path.join(root, "data", "live_state_acctb.json"), {"adapter": "paper", "ledger": [
        {"t": e2, "side": "sell", "qty": 1, "entry_t": e2, "result": {"ok": True, "adapter": "paper"}},
        {"t": e2 + 3600, "side": "exit", "qty": 1, "entry_t": e2, "reason": "STOP", "pnl": -80.0, "result": {"ok": True}}]})
    dpw = os.path.join(tmp, "dpw")
    wjson(os.path.join(dpw, "days", "2026-11-18", "review.json"), {"day": "2026-11-18", "text": "ZEUS Nov 18: test review"})
    return root, nt, dpw


def make_cloud_data(tmp, end_t):
    """data/ like the TradingView exports: NQ 1m + 5m, ES 5m up to end_t (the PC's prices, same contract), the roll files."""
    d = os.path.join(tmp, "data")
    os.makedirs(d, exist_ok=True)
    nq1 = [r for r in bars_1m(DAYS[:3], 21000.0) if r[0] <= end_t]
    es1 = [r for r in bars_1m(DAYS[:3], 6000.0) if r[0] <= end_t]
    for name, rows in (("NQ_1m", nq1), ("NQ_5m", [r for r in agg5(nq1) if r[0] + 300 <= end_t + 60]),
                       ("ES_5m", [r for r in agg5(es1) if r[0] + 300 <= end_t + 60])):
        with open(os.path.join(d, f"{name}.csv"), "w") as fh:
            fh.write("time,open,high,low,close,volume\n" + "".join(",".join(str(x) for x in r) + "\n" for r in rows))
    wjson(os.path.join(d, "NQ_rolls.json"), {"sym": "NQ", "anchor": "NQZ26", "rolls": []})
    wjson(os.path.join(d, "ES_rolls.json"), {"sym": "ES", "anchor": "ESZ26", "rolls": []})
    return d


def csv_rows(path):
    with open(path) as fh:
        return fh.read().splitlines()


# ================================================================================================ PC side
def pc_checks(tmp, fake, env, root, nt, dpw, now):
    topic = env["LE_DATAFEED_TOPIC"]
    w = os.path.join(tmp, "feedw")
    spawned = []

    def sp(work):
        spawned.append(work)
        return DEAD_PID

    fake.clock = lambda: now
    c0 = len(fake.calls)
    r = DF.maybe_answer(now=ts("2026-11-18", 10, 0), env=env, say=lambda *a: None, work=w, spawn_fn=sp)
    check("a. PC: during the session (Wed 10:00 ET) no call to ntfy at all", r is None and len(fake.calls) == c0, fake.calls[c0:])
    r = DF.maybe_answer(now=now, env={**env, "LE_DATAFEED": "0"}, say=lambda *a: None, work=w, spawn_fn=sp)
    check("a. PC: LE_DATAFEED=0 = off, no call", r is None and len(fake.calls) == c0)
    r = DF.maybe_answer(now=now, env=env, say=lambda *a: None, work=w, spawn_fn=sp)
    check("a. PC: outside the session, no request: one GET of the topic (+ at most one read of ntfy's count, night-of-backfill), "
          "nothing started", r is None and fake.n("GET", topic) == 1 and not spawned and len(fake.calls) - c0 - 1 ==
          sum(1 for m, p in fake.calls[c0:] if m == "GET" and p == "/v1/account") <= 1, fake.calls[c0:])
    for bad in ({"v": 1, "kind": "le-data-req", "id": "abc123", "since": "2026-11-1"},
                {"v": 1, "kind": "le-data-req", "id": "AB", "since": "2026-11-16"},
                {"v": 1, "kind": "le-live", "id": "abc123", "since": "2026-11-16"},
                {"v": 2, "kind": "le-data-req", "id": "abc123", "since": "2026-11-16"}):
        fake.post(topic, bad)
    fake.post(topic, {"v": 1, "kind": "le-data-req", "id": "old0001", "since": "2026-11-16"}, t=now - 7 * 3600)
    r = DF.maybe_answer(now=now, env=env, say=lambda *a: None, work=w, spawn_fn=sp)
    check("a. PC: bad / foreign / 7 h old requests are ignored", r is None and not spawned, spawned)
    req = fake.post(topic, {"v": 1, "kind": "le-data-req", "id": "req0001", "since": "2026-11-16"})
    r = DF.maybe_answer(now=now, env=env, say=lambda *a: None, work=w, spawn_fn=lambda work: spawned.append(work) or os.getpid())
    check("b. PC: a request starts ONE child (pending.json = the ask)", r and r["req"]["id"] == "req0001" and len(spawned) == 1
          and DF._read_json(os.path.join(w, "pending.json"), {}).get("since") == "2026-11-16", (r, spawned))
    r2 = DF.maybe_answer(now=now + 300, env=env, say=lambda *a: None, work=w, spawn_fn=sp)
    check("b. PC: not again while that child runs", r2 is None and len(spawned) == 1)
    os.remove(os.path.join(w, "running.json"))

    # the child: pack + send
    fake.fail_put = 500
    a1 = DF.answer(DF._read_json(os.path.join(w, "pending.json")), now=now + 30, root=root, work=w, folder=nt, env=env,
                   archive_root=os.path.join(tmp, "noarch"), dp_work=dpw)
    st = DF._state(w)
    check("c. PC: a failed upload is recorded, not raised", a1["ok"] is False and "500" in str(a1.get("why")) and
          st.get("last_error", {}).get("req") == "req0001", a1)
    for k in range(4):                                             # tries 2, 3, then given up (MAX_TRIES = 3)
        DF.maybe_answer(now=now + 600 + 300 * k, env=env, say=lambda *a: None, work=w, spawn_fn=sp)
        try:
            os.remove(os.path.join(w, "running.json"))
        except OSError:
            pass
    check("c. PC: a request whose upload keeps failing is started at most 3 times", len(spawned) == 3, len(spawned))

    fake.fail_put = None
    req2 = fake.post(topic, {"v": 1, "kind": "le-data-req", "id": "req0002", "since": "2026-11-16"}, t=now + 1700)
    t2 = now + 1800
    fake.clock = lambda: t2
    r = DF.maybe_answer(now=t2, env=env, say=lambda *a: None, work=w, spawn_fn=sp)
    a2 = DF.answer(DF._read_json(os.path.join(w, "pending.json")), now=t2 + 20, root=root, work=w, folder=nt, env=env,
                   archive_root=os.path.join(tmp, "noarch"), dp_work=dpw)
    msg = fake.msgs[topic][-1]
    meta = json.loads(msg["message"])
    blob = fake.files[msg["id"]][0]
    check("d. PC: answer = ONE attachment; meta has the request, days, bytes, sha256 (= the file), the bar rows",
          a2["ok"] and meta["kind"] == "le-data" and meta["req"] == "req0002" and meta["bytes"] == len(blob) == msg["attachment"]["size"]
          and meta["sha256"] == hashlib.sha256(blob).hexdigest() and meta["from"] == "2026-11-16" and meta["to"] == "2026-11-19"
          and meta["days"] == 4 and set(meta["bars"]) == {"NQ_1m", "NQ_5m", "ES_1m", "ES_5m"}
          and meta["bars"]["NQ_1m"]["root"] == "MNQ" and len(blob) <= DF.MAX_ZIP, (a2, meta))
    check("d. PC: the unfinished Nov 19 session (Wed 20:00 ET) is marked partial", meta["partial"] == ["2026-11-19"], meta["partial"])
    z = zipfile.ZipFile(io.BytesIO(blob))
    names = z.namelist()
    check("d. PC: day folders like the data branch: bars (MNQ + MES, 1m + 5m), trades, manifest, the nightly review",
          "days/2026-11-17/bars/MNQ_1m.csv.gz" in names and "days/2026-11-18/bars/MES_5m.csv.gz" in names
          and "days/2026-11-17/trades.jsonl.gz" in names and "days/2026-11-18/review.json" in names
          and all(DF.DAY_FILE.match(n) for n in names) and not any("2026-11-13" in n for n in names), names)
    allb = b"".join(gzip.decompress(z.read(n)) if n.endswith(".gz") else z.read(n) for n in names)
    check("d. PC: privacy: no full account id, no balance, no Windows path, no OIF line anywhere in the zip",
          ACCT_A.encode() not in allb and ACCT_B.encode() not in allb and b"49192.78" not in allb and b"\"balance\"" not in allb
          and b"NinjaTrader 8" not in allb and b"PLACE;" not in allb and b"...1234" in allb,
          [k for k, bad in (("acct A", ACCT_A.encode() in allb), ("acct B", ACCT_B.encode() in allb), ("balance", b"49192.78" in allb),
                            ("balance key", b"\"balance\"" in allb), ("path", b"NinjaTrader 8" in allb), ("OIF", b"PLACE;" in allb),
                            ("no last 4", b"...1234" not in allb)) if bad])
    tr = [json.loads(x) for x in gzip.decompress(z.read("days/2026-11-17/trades.jsonl.gz")).decode().splitlines()]
    check("d. PC: the closed-trade log of the day: entry + exit rows, tagged bot / acct / mode",
          {(r["side"], r["bot"], r["mode"]) for r in tr} >= {("buy", "zlarior", "live"), ("exit", "zlarior", "live")}
          and any(r.get("acct") == "b25k_2" for r in tr) and any(r.get("pnl") == 156.3 for r in tr), tr)
    r = DF.maybe_answer(now=t2 + 300, env=env, say=lambda *a: None, work=w, spawn_fn=sp)
    check("e. PC: an answered request is not answered again", r is None and len(spawned) == 4, len(spawned))
    st = DF._state(w)
    st["sent"] = [{"t": t2, "day": dt.datetime.fromtimestamp(t2, ET).date().isoformat(), "req": f"x{i}"} for i in range(DF.DAILY_CAP)]
    DF._write_json(os.path.join(w, "state.json"), st)
    fake.post(topic, {"v": 1, "kind": "le-data-req", "id": "req0003", "since": "2026-11-16"}, t=t2 + 500)
    r = DF.maybe_answer(now=t2 + 600, env=env, say=lambda *a: None, work=w, spawn_fn=sp)
    check("e. PC: at most DAILY_CAP answers a day", r is None and DF._state(w).get("held_why", "").startswith(str(DF.DAILY_CAP)), DF._state(w))
    real_build = DF.build
    DF.build = lambda *a, **k: (_ for _ in ()).throw(RuntimeError(f"cannot read C:\\Users\\owner\\le_feed\\MNQ_1m.csv of {ACCT_A}"))
    try:
        ae = DF.answer({"id": "req0009", "since": "2026-11-16"}, now=t2 + 700, root=root, work=os.path.join(tmp, "errw"), folder=nt, env=env)
    finally:
        DF.build = real_build
    em = json.loads(fake.msgs[topic][-1]["message"])
    pe = DF.parse_answer(fake.msgs[topic][-1], t2 + 700, fake.base)
    check("e. PC: a pack that breaks posts a short error answer (scrubbed), so Claude reads why instead of waiting",
          ae.get("error") and em.get("req") == "req0009" and em.get("days") == 0 and "<path>" in em.get("error", "")
          and ACCT_A not in json.dumps(em) and pe and pe.get("error") and pe.get("url") is None, (ae, em))
    small_blob, small_meta = DF.build("2026-11-16", t2, root, nt, os.path.join(tmp, "noarch"), None, dpw, max_zip=60_000)
    check("e. PC: over the size cap: oldest days first, 'more' set, never above the cap",
          small_meta["more"] and small_meta["from"] == "2026-11-16" and small_meta["days"] < 4 and len(small_blob) <= 60_000, small_meta)
    return blob, meta, msg


# ================================================================================================ cloud side
def cloud_checks(tmp, fake, env, blob, meta, msg):
    topic = env["LE_DATAFEED_TOPIC"]
    now = fake.clock()
    good = DF.parse_answer(msg, now, fake.base)
    check("f. cloud: the answer parses (url on the same server, size + sha256 announced)", good and good["req"] == "req0002"
          and good["url"].startswith(fake.base + "/file/"), good)
    bad_base = DF.parse_answer(msg, now, "https://ntfy.sh")
    m2 = json.loads(json.dumps(msg))
    m2["attachment"]["size"] += 1
    m3 = json.loads(json.dumps(msg))
    m3["attachment"]["expires"] = int(now) - 1
    check("f. cloud: refused: another server, a size other than announced, an expired file",
          bad_base is None and DF.parse_answer(m2, now, fake.base) is None and DF.parse_answer(m3, now, fake.base) is None)
    fake.tamper = True
    try:
        PULL.fetch_bundle(good)
        tam = "accepted"
    except ValueError as e:
        tam = str(e)
    fake.tamper = False
    check("f. cloud: a download that differs from the announced bytes is refused", "differs" in tam or "bytes" in tam, tam)

    def evil(entries):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, b in entries:
                z.writestr(n, b)
        return buf.getvalue()
    out = os.path.join(tmp, "evil_out")
    man = json.dumps({"day": "2026-11-18", "files": {}}).encode()
    cases = {"path escape": [("days/2026-11-18/manifest.json", man), ("days/2026-11-18/../../../x.py", b"x")],
             "unknown file": [("days/2026-11-18/manifest.json", man), ("days/2026-11-18/run.py", b"x")],
             "day mismatch": [("days/2026-11-17/manifest.json", man)],
             "checksum": [("days/2026-11-18/manifest.json", json.dumps({"day": "2026-11-18", "files": {"trades.jsonl.gz": {"sha256": "0" * 64}}}).encode()),
                          ("days/2026-11-18/trades.jsonl.gz", gzip.compress(b"{}\n"))],
             "not a zip": None}
    res = {}
    for k, ents in cases.items():
        try:
            DF.extract(evil(ents) if ents else b"PK not really", out)
            res[k] = "accepted"
        except ValueError:
            res[k] = "refused"
    check("f. cloud: a bad bundle is refused whole (escape, unknown file, wrong day, checksum, not a zip), nothing written",
          set(res.values()) == {"refused"} and not os.path.exists(out), res)


def flow_checks(tmp, fake, env, root, nt, dpw, now, cap=DF.MAX_ZIP, label="g"):
    """The real command: python tools/data_pull.py --latest, the PC answering on its 5-minute tick (fake clock)."""
    base = os.path.join(tmp, f"flow_{label}")
    os.makedirs(base, exist_ok=True)
    end_t = ts("2026-11-16", 12, 0)
    data = make_cloud_data(base, end_t)
    out = os.path.join(base, "pc_days")
    pcw = os.path.join(base, "feedw")
    clock = Clock(now)
    fake.clock = clock.time
    nxt = [now + 120]
    answered = []

    def spawn_sync(work):
        req = DF._read_json(os.path.join(work, "pending.json"))
        answered.append(DF.answer(req, now=int(clock.t), root=root, work=work, folder=nt, env=env,
                                  archive_root=os.path.join(tmp, "noarch"), dp_work=dpw, max_zip=cap))
        return DEAD_PID

    def fake_sleep(s):
        clock.t += s
        if clock.t >= nxt[0]:
            nxt[0] += 300
            DF.maybe_answer(now=int(clock.t), env=env, say=lambda *a: None, work=pcw, spawn_fn=spawn_sync)

    class T:
        time = staticmethod(clock.time)
        sleep = staticmethod(fake_sleep)

    old_time, old_env = PULL.time, {k: os.environ.get(k) for k in env}
    PULL.time = T
    os.environ.update(env)
    before = {n: csv_rows(os.path.join(data, f"{n}.csv")) for n in ("NQ_1m", "NQ_5m", "ES_5m")}
    try:
        buf = io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(buf):
            rc = PULL.main(["--latest", "--data", data, "--out", out, "--queue", os.path.join(base, "q.jsonl")])
        txt = buf.getvalue()
        posts1 = fake.n("POST", env["LE_DATAFEED_TOPIC"])
        after = {n: csv_rows(os.path.join(data, f"{n}.csv")) for n in ("NQ_1m", "NQ_5m", "ES_5m")}
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = PULL.main(["--latest", "--data", data, "--out", out, "--queue", os.path.join(base, "q.jsonl")])
        txt2 = buf2.getvalue()
        again = {n: csv_rows(os.path.join(data, f"{n}.csv")) for n in ("NQ_1m", "NQ_5m", "ES_5m")}
        posts2 = fake.n("POST", env["LE_DATAFEED_TOPIC"])
    finally:
        PULL.time = old_time
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return {"rc": rc, "rc2": rc2, "txt": txt, "txt2": txt2, "before": before, "after": after, "again": again, "posts1": posts1,
            "posts2": posts2, "answered": answered, "out": out, "data": data, "end_t": end_t}


def flow_asserts(R, label, want_rounds=1):
    nq_b, nq_a = R["before"]["NQ_1m"], R["after"]["NQ_1m"]
    times = [int(x.split(",")[0]) for x in nq_a[1:]]
    last_ok = ts("2026-11-18", 16, 59)
    new = [t for t in times if t > R["end_t"]]
    expect = [t for d in ("2026-11-16", "2026-11-17", "2026-11-18") for t in session_minutes(d) if t > R["end_t"]]
    check(f"{label}. --latest: the command asked, the PC answered on its tick, rc 0", R["rc"] == 0 and len(R["answered"]) == want_rounds
          and all(a["ok"] for a in R["answered"]), (R["rc"], R["txt"][-600:], R["answered"]))
    check(f"{label}. --latest: NQ 1m = the export untouched + every PC bar after it to Wed 16:59 ET, no duplicate",
          nq_a[:len(nq_b)] == nq_b and new == expect and len(times) == len(set(times)) and max(times) == last_ok,
          (len(nq_b), len(nq_a), len(new), len(expect)))
    t5 = [int(x.split(",")[0]) for x in R["after"]["NQ_5m"][1:]]
    e5 = [int(x.split(",")[0]) for x in R["after"]["ES_5m"][1:]]
    check(f"{label}. --latest: NQ 5m and ES 5m (from the MES chart) appended to Wed 16:55 ET, no duplicate",
          max(t5) == ts("2026-11-18", 16, 55) and max(e5) == ts("2026-11-18", 16, 55) and len(t5) == len(set(t5)) and
          len(e5) == len(set(e5)) and R["after"]["ES_5m"][:len(R["before"]["ES_5m"])] == R["before"]["ES_5m"], (max(t5), max(e5)))
    k = ts("2026-11-16", 12, 0)
    row = next((x for x in R["after"]["NQ_5m"][1:] if int(x.split(",")[0]) == k), "")
    whole = agg5([r for r in bars_1m(["2026-11-16"], 21000.0) if k <= r[0] < k + 300])[0]
    check(f"{label}. --latest: the 5m bar across the export's end (12:00) is the PC's whole bar, not 4 of its 5 minutes",
          [float(x) for x in row.split(",")[1:5]] == [float(x) for x in whole[1:5]], (row, whole))
    check(f"{label}. --latest: the unfinished Thu session stays out of data/ (kept in pc_days)",
          not any(t >= ts("2026-11-18", 18, 0) for t in times + t5 + e5)
          and json.load(open(os.path.join(R["out"], "2026-11-19", "manifest.json")))["partial"] is True, R["txt"][-400:])
    check(f"{label}. --latest: trades in data/pc_days for tools/live_trades.py", os.path.exists(os.path.join(R["out"], "2026-11-17", "trades.jsonl.gz")))
    check(f"{label}. --latest again: the answer already on the topic is used (no new request), nothing added",
          R["rc2"] == 0 and R["posts2"] == R["posts1"] and R["again"] == R["after"], (R["rc2"], R["txt2"][-400:]))


def edge_check(R):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import edge_health as EH
    old = EH.DATA
    try:
        EH.DATA = R["data"]
        rows = {}
        for nm in ("NQ_1m", "NQ_5m", "ES_5m"):
            t = EH._last_t(os.path.join(R["data"], f"{nm}.csv"))
            rows[nm] = EH._iso(t)
    finally:
        EH.DATA = old
    check("h. edge_health reads the fresh end of data/ (Nov 18 16:59 ET)", rows["NQ_1m"].startswith("2026-11-18 16:59")
          and rows["NQ_5m"].startswith("2026-11-18 16:55"), rows)


# ================================================================================================ the datapipe switch
def datapipe_checks(tmp, root, nt):
    class Rec(DP.Git):
        def __init__(self):
            super().__init__(os.path.join(tmp, "rec.git"), cwd=tmp, exe="git")
            self.calls = []

        def run(self, args, inp=None, env=None, timeout=60, bare=True):
            self.calls.append(list(args))
            if args and args[0] in ("init", "config"):
                os.makedirs(os.path.join(self.git_dir, "objects"), exist_ok=True)
                return (0, "", "") if args[0] == "init" else (1, "", "")
            return 1, "", "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
    w = os.path.join(tmp, "dp_run")
    os.makedirs(w, exist_ok=True)
    wjson(os.path.join(w, "state.json"), {"fails": 3})
    g = Rec()
    old = os.environ.pop("LE_DATAPIPE_GIT", None)
    try:
        r = DP.run(now=ts("2026-11-18", 17, 30), root=root, work=w, folder=nt, g=g, notify=lambda *a, **k: None,
                   emit=lambda *a, **k: None, build_twin=False, edge={}, archive_root=os.path.join(tmp, "noarch"))
        st = DP._read_json(os.path.join(w, "state.json"), {})
        rv = json.load(open(os.path.join(w, "days", "2026-11-18", "review.json")))
        check("i. datapipe: git push OFF by default: no git call at all, no error, the days still packed + reviewed",
              not g.calls and not r["errors"] and r["pushed"] is None and "2026-11-18" in r["days"] and "ntfy" in r.get("note", ""), (g.calls[:3], r))
        check("i. datapipe: the review no longer says the push failed (fails reset), done for the day",
              st.get("fails") == 0 and not any(i.get("key") == "pipe" for i in rv.get("items") or []) and st.get("done_day") == "2026-11-18", st)
        check("i. datapipe: LE_DATAPIPE_GIT=1 turns the push back on", DP.git_enabled({"LE_DATAPIPE_GIT": "1"}) and not DP.git_enabled({}))
        old_bu = DP.backup_url
        DP.backup_url = lambda root=None, env=None: "https://example.invalid/backup.git"
        try:
            g2 = Rec()
            r2 = DP.run(now=ts("2026-11-18", 17, 40), root=root, work=os.path.join(tmp, "dp_run2"), folder=nt, g=g2, git=True,
                        notify=lambda *a, **k: None, emit=lambda *a, **k: None, build_twin=False, edge={},
                        archive_root=os.path.join(tmp, "noarch"))
        finally:
            DP.backup_url = old_bu
        check("i. datapipe: run --git still tries the backup (and fails cleanly without a sign-in)",
              any("ls-remote" in c for c in g2.calls) and r2["pushed"] and r2["pushed"]["ok"] is False, (g2.calls[:2], r2.get("pushed")))
    finally:
        if old is not None:
            os.environ["LE_DATAPIPE_GIT"] = old
    calls = []
    pid = DP.maybe_run(now=ts("2026-11-18", 20, 0), say=lambda *a: None, env={"LE_DATAPIPE": "1"}, work=os.path.join(tmp, "mr"),
                       spawn_fn=lambda work: None, root=root, feed=lambda **k: calls.append(k))
    check("j. the 5-minute hook (datapipe.maybe_run) asks the data feed every call", pid is None and len(calls) == 1
          and calls[0]["now"] == ts("2026-11-18", 20, 0), calls)
    src = open(os.path.join(ROOT, "engine", "ops_checks.py"), encoding="utf-8").read()
    check("j. wired: the ops task (every 5 min) calls datapipe.maybe_run", "datapipe.maybe_run(now=now" in src)


def main():
    tmp = tempfile.mkdtemp(prefix="le_df_")
    fake = FakeNtfy()
    env = {"LE_DATAFEED_BASE": fake.base, "LE_DATAFEED_TOPIC": "test-data-" + secrets.token_hex(4), "LE_PR_NO_NET": ""}
    try:
        now = ts("2026-11-18", 20, 0)                              # Wednesday 20:00 ET: outside the session
        root, nt, dpw = make_pc(tmp, now)
        blob, meta, msg = pc_checks(tmp, fake, env, root, nt, dpw, now)
        cloud_checks(tmp, fake, env, blob, meta, msg)
        env2 = {**env, "LE_DATAFEED_TOPIC": "test-flow-" + secrets.token_hex(4)}
        R = flow_checks(tmp, fake, env2, root, nt, dpw, now + 7200)
        flow_asserts(R, "g")
        edge_check(R)
        env3 = {**env, "LE_DATAFEED_TOPIC": "test-more-" + secrets.token_hex(4)}
        R3 = flow_checks(tmp, fake, env3, root, nt, dpw, now + 7200, cap=60_000, label="g2")
        flow_asserts(R3, "g2 (size cap: asked again from the next day)", want_rounds=len(R3["answered"]) if len(R3["answered"]) > 1 else 99)
        datapipe_checks(tmp, root, nt)
    finally:
        fake.srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\ndata feed over ntfy: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
