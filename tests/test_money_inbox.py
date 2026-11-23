"""MONEY INBOX (tools/money_inbox_server.py + tools/bat/MONEY_INBOX.bat, 2026-11-14): the append-only inbox for the iPhone Shortcut. Checks:
  a. a real server on a free port: POST /inbox with JSON or plain text appends one checked line to <home>/money_inbox/cash.jsonl and
     answers in words; GET /health says nothing about money; every other path / method is 404 / 405; nothing else is ever written
  b. the guard: a Funnel (internet) request is refused, a proxied request without Tailscale's user is refused, the allow-list is honoured,
     a request from this PC itself is fine; bodies over 2 KB, no Content-Length, bad amounts / dates / kinds are refused; 30 a minute
  c. privacy: a card number typed in the text is masked before it is written
  d. the line is read by tools/money_import.py: a cash expense in the chosen category, a balance into the net-worth file, once each
  e. the script: tools/bat/MONEY_INBOX.bat is ASCII + CRLF, every goto target exists, it serves on :8443 with tailscale serve and never turns on
     Funnel, it never touches the bot server's port 8766; the server binds 127.0.0.1 only, stdlib only, no subprocess
    python -X utf8 -m tests.test_money_inbox
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import money_inbox_server as IB  # noqa: E402
import money_import as MI  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def call(port, method, path, body=None, headers=None, raw=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = raw if raw is not None else (json.dumps(body).encode() if isinstance(body, dict) else (body.encode() if isinstance(body, str) else None))
    h = dict(headers or {})
    if data is not None and "Content-Length" not in h:
        h["Content-Length"] = str(len(data))
    if isinstance(body, dict):
        h.setdefault("Content-Type", "application/json")
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    txt = r.read().decode()
    c.close()
    try:
        return r.status, json.loads(txt)
    except ValueError:
        return r.status, txt


def lines(home):
    p = os.path.join(home, "money_inbox", "cash.jsonl")
    return [json.loads(x) for x in open(p, encoding="utf-8").read().splitlines()] if os.path.exists(p) else []


def main():
    tmp = tempfile.mkdtemp(prefix="money-inbox-test-")
    home = os.path.join(tmp, "home")
    srv = IB.serve(home, 0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    TS = {"X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": "pat@example.com"}
    try:
        st, j = call(port, "POST", "/inbox", {"amount": 12.5, "what": "Tacos", "cat": "food"}, TS)
        check("a. JSON expense through Tailscale: 200, 'Saved: $12.50 Tacos (food)'", st == 200 and j.get("saved") == "Saved: $12.50 Tacos (food)", (st, j))
        st, j = call(port, "POST", "/inbox", "8 coffee food", {**TS, "Content-Type": "text/plain"})
        check("a. plain text '8 coffee food' works too", st == 200 and j.get("saved") == "Saved: $8 coffee (food)", (st, j))
        st, j = call(port, "POST", "/inbox", {"kind": "balance", "name": "Checking", "amount": "3,200.55"}, TS)
        check("a. a balance: 'Saved: Checking balance $3,201'", st == 200 and j.get("saved", "").startswith("Saved: Checking balance"), (st, j))
        st, j = call(port, "POST", "/inbox", {"kind": "income", "amount": 40, "what": "Sold a chair 4111 1111 1111 1111"}, TS)
        L = lines(home)
        check("c. a card number typed in the text is masked before it is written", st == 200 and "4111" not in json.dumps(L) and L[-1]["what"].startswith("Sold a chair"), L[-1:])
        check("a. four lines appended, each with an id, a time, a kind, an amount and a date", len(L) == 4 and all({"id", "t", "kind", "amount", "date"} <= set(x) for x in L), L)
        st, j = call(port, "GET", "/health", headers=TS)
        check("a. GET /health: ok and nothing about money", st == 200 and j == {"ok": True, "kind": "olympus-money-inbox", "writes": "append only"}, (st, j))
        bad = [call(port, "GET", "/inbox", headers=TS)[0], call(port, "GET", "/money_inbox/cash.jsonl", headers=TS)[0], call(port, "POST", "/api/arm", {"x": 1}, TS)[0],
               call(port, "PUT", "/inbox", {"amount": 1}, TS)[0], call(port, "DELETE", "/inbox", headers=TS)[0]]
        check("a. nothing can be read back, no other route, no PUT / DELETE: 404 404 404 405 405", bad == [404, 404, 404, 405, 405], bad)
        # b. the guard
        st, j = call(port, "POST", "/inbox", {"amount": 5, "what": "x"}, {**TS, "Tailscale-Funnel-Request": "?1"})
        check("b. a Funnel (internet) request is refused", st == 403 and "never the internet" in j["error"], (st, j))
        st, j = call(port, "POST", "/inbox", {"amount": 5, "what": "x"}, {"X-Forwarded-For": "1.2.3.4"})
        check("b. through a proxy but no signed-in Tailscale user: refused", st == 403, (st, j))
        st, j = call(port, "POST", "/inbox", {"amount": 5, "what": "from the PC"})
        check("b. from this PC itself (no proxy headers): fine", st == 200, (st, j))
        os.makedirs(os.path.join(home, "money"), exist_ok=True)
        MI.write_json(os.path.join(home, "money", "inbox.json"), {"allow": ["Pat@Example.com"]})
        ok1 = call(port, "POST", "/inbox", {"amount": 1, "what": "allowed"}, TS)[0]
        ok2 = call(port, "POST", "/inbox", {"amount": 1, "what": "stranger"}, {**TS, "Tailscale-User-Login": "someone@else.com"})[0]
        check("b. the allow-list: your login passes (any case), another tailnet user is refused", (ok1, ok2) == (200, 403), (ok1, ok2))
        os.remove(os.path.join(home, "money", "inbox.json"))
        n0 = len(lines(home))
        refusals = [call(port, "POST", "/inbox", raw=b"x" * 3000, headers={**TS, "Content-Length": "3000"})[0],
                    call(port, "POST", "/inbox", {"amount": -5, "what": "neg"}, TS)[0], call(port, "POST", "/inbox", {"amount": "abc"}, TS)[0],
                    call(port, "POST", "/inbox", {"amount": 5, "kind": "trade"}, TS)[0], call(port, "POST", "/inbox", {"amount": 5, "date": "2031-01-01"}, TS)[0],
                    call(port, "POST", "/inbox", {"amount": 2_000_000}, TS)[0], call(port, "POST", "/inbox", "not json at all", {**TS, "Content-Type": "text/plain"})[0],
                    call(port, "POST", "/inbox", {"kind": "balance", "amount": 5}, TS)[0]]
        check("b. refused: 3 KB body 413, negative / junk amount, unknown kind, a future date, $2M, junk text, a nameless balance (400)",
              refusals == [413, 400, 400, 400, 400, 400, 400, 400] and len(lines(home)) == n0, refusals)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.putrequest("POST", "/inbox")
        for k, v in TS.items():
            c.putheader(k, v)
        c.endheaders()
        r = c.getresponse()
        check("b. no Content-Length: 411", r.status == 411, r.status)
        c.close()
        inbox = IB.Inbox(home, now=lambda: 1_800_000_000.0)
        got = [inbox.rate() for _ in range(31)]
        check("b. at most 30 posts a minute", got.count(True) == 30 and got[-1] is False)
        written = sorted(os.listdir(os.path.join(home, "money_inbox")))
        check("a. the only file it ever writes is money_inbox/cash.jsonl", written == ["cash.jsonl"], written)
        # d. money_import reads it
        out = os.path.join(tmp, "out")
        doc = MI.run(home, out, None, MI.today_et(), quiet=True)
        cls = MI.classify(MI.load_ledger(os.path.join(home, "money", "ledger.json")), MI.DEFAULT_RULES_DOC)
        tacos = [r for r in cls if r["desc"].startswith("Tacos")]
        bal = MI.load_balances(os.path.join(home, "money", "balances.json"))
        chk = [a for a in bal["accounts"] if a["name"] == "Checking"]
        check("d. money_import reads the inbox: Tacos is a $12.50 food expense; the Checking balance is in the net-worth file",
              tacos and tacos[0]["amount"] == -12.5 and tacos[0]["cat"] == "food" and chk and chk[0]["usd"] == 3200.55, (tacos[:1], chk))
        n_rows = doc["data"]["rows"]
        MI.set_balance(bal, "Checking", 100.0)
        MI.write_json(os.path.join(home, "money", "balances.json"), bal)
        doc2 = MI.run(home, out, None, MI.today_et(), quiet=True)
        bal2 = MI.load_balances(os.path.join(home, "money", "balances.json"))
        check("d. read again: no row twice, and an old balance line does not overwrite a newer balance", doc2["data"]["rows"] == n_rows and [a["usd"] for a in bal2["accounts"] if a["name"] == "Checking"] == [100.0],
              (doc2["data"]["rows"], n_rows))
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    # e. the script and the source
    bat = open(os.path.join(ROOT, "tools/bat/MONEY_INBOX.bat"), "rb").read()
    txt = bat.decode("ascii", "replace")
    labels = {m.lower() for m in re.findall(r"^:(\w+)", txt, re.M)}
    gotos = {m.lower() for m in re.findall(r"goto :(\w+)", txt, re.I)} | {m.lower() for m in re.findall(r"call :(\w+)", txt, re.I)}
    check("e. tools/bat/MONEY_INBOX.bat: ASCII, CRLF only, every goto / call target exists", all(c < 128 for c in bat) and bat.count(b"\n") == bat.count(b"\r\n") and gotos <= labels, gotos - labels)
    check("e. it serves the inbox on :8443 with tailscale serve, never Funnel, never the bot server's 8766, and has an 'off' undo",
          "serve --bg --yes --https=8443 http://127.0.0.1:8767" in txt and not re.search(r"(?:%TS%\"|tailscale)\s+funnel", txt, re.I) and "8766" not in txt and ":off" in txt and "OlympusMoneyInbox" in txt)
    src = open(os.path.join(ROOT, "tools", "money_inbox_server.py"), encoding="utf-8").read()
    imports = set(re.findall(r"^(?:from|import) ([a-zA-Z_.]+)", src, re.M))
    check("e. the server: stdlib (+ money_import), binds 127.0.0.1 only, no subprocess / os.system / eval, never imports the bot",
          imports <= {"__future__", "argparse", "datetime", "json", "os", "re", "sys", "threading", "time", "uuid", "http.server", "money_import"}
          and not re.search(r"subprocess|os\.system|\beval\(|\bexec\(|engine|server\.py|ninjatrader", src.split('"""', 2)[2]) and "0.0.0.0" not in src, imports)
    try:
        IB.serve(home, 0, host="0.0.0.0")
        check("e. refuses to listen on every network interface", False)
    except SystemExit:
        check("e. refuses to listen on every network interface", True)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
