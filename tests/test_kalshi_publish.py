"""Kalshi in Jarvis (engine/kalshi_publish.py + tools/kalshi_kit/public/kalshi_status_vm.py, owner 2026-11-01): the Kalshi
bot's numbers -> kalshi.json on the branch `kalshi` of the Pages repo, which the Kalshi page (tools/web_public/kalshi/) and
the Jarvis card read. No real keys and no network beyond 127.0.0.1. Checks:
  a. clean(): only the contract's keys leave, secrets dropped, local paths redacted, numbers as numbers, lists capped,
     junk never raises
  b. read(): missing / broken / non-object files give an error, a file without "t" takes the file's time, oversize is trimmed
  c. push_once(): one orphan commit on refs/heads/kalshi of a local bare repo holding exactly kalshi.json (replaced on the next
     push, no history); the real live.json push keeps its file name
  d. loop(): pushes when the file changed, keeps quiet when it did not (until the keep-alive), waits while the file is missing
  e. contract v2: strategies (<= 10) and equity (<= 500, downsampled) only when given; v1 unchanged; fit(); same patterns
  f. ET days without tzdata = zoneinfo (2021-2027, DST edges); titles from tickers
  g. the bot's own files (trades.db read-only, spec section 7): P&L across ET midnight and today's DST switch, week, days,
     open bets, trades (UP/DOWN), strategies, equity, paused / stale states; it never opens .env, keys/ or sniper.db
  h. API mode against a mock Kalshi that verifies RSA-PSS and Ed25519 signatures (keys made at run time): P&L math across
     ET midnight, positions, trades, equity, cheap loop rounds, 429 stops at once, redirects refused
  i. GET-only: anything else is refused before a request; only Kalshi's API can be the base URL
  j. redaction: key id, key path, PEM, signatures, paths and IPs never reach errors, logs or the payload
  k. the standalone file copied outside the repo (python -I) and the module give identical JSON (API, bot files, status file)
  l. --ssh through a stand-in srv.py (same code shape as the PC's) = reading the files directly
  m. pushes to a local bare repo: the kit's own, --cron (only on a change), the module's; deploy-key SSH settings
  n. the public kit holds no VM address, tunnel URL, private key or private folder ids
    python -X utf8 -m tests.test_kalshi_publish      (temp folders only; nothing else touched)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import kalshi_publish as kp  # noqa: E402
from engine import live_publish as lp  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def part_a():
    raw = {**kp.SAMPLE, "api_key": "sk-123", "private_key_path": "C:\\Users\\me\\kalshi.pem", "secret": "x", "extra": {"a": 1},
           "status": "log at C:\\Users\\me\\bot\\log.txt", "balance": "512.34",
           "positions": [{**kp.SAMPLE["positions"][0], "token": "t", "contracts": "10"}] * 100,
           "trades": [kp.SAMPLE["trades"][0]] * 100, "days": [["2026-10-01", 1.0]] * 300}
    c = kp.clean(raw, now=1793548900)
    s = json.dumps(c)
    check("a. only the contract's keys (no api_key / private key / secret / unknown keys)",
          set(c) == set(kp.TOP) | {"v", "kind", "positions", "trades", "days", "pub_t"} and "sk-123" not in s and "token" not in s, sorted(c))
    check("a. local paths redacted", "Users" not in s and "<path>" in c["status"], c["status"])
    check("a. numbers as numbers", c["balance"] == 512.34 and c["positions"][0]["contracts"] == 10.0 and c["kind"] == "kalshi" and c["v"] == 1, c["balance"])
    check("a. lists capped (positions 60, trades 40, days 120)", (len(c["positions"]), len(c["trades"]), len(c["days"])) == (60, 40, 120))
    check("a. the sample keeps its numbers", c["today_pnl"] == 18.5 and c["running"] is True and c["mode"] == "paper" and c["t"] == kp.SAMPLE["t"])
    j = kp.clean("junk", now=5)
    check("a. junk input never raises (an empty card)", j["kind"] == "kalshi" and j["positions"] == [] and j["t"] == 5, j)
    d = kp.clean({"days": [{"day": "2026-10-30", "pnl": "2.5"}, ["2026-10-31", "x"], "bad"]}, now=5)
    check("a. days as [day, pnl] pairs or {day, pnl}; bad rows dropped", d["days"] == [["2026-10-30", 2.5]], d["days"])


def part_b(tmp):
    p, err = kp.read(os.path.join(tmp, "missing.json"))
    check("b. missing file -> error, no payload", p is None and "not found" in err, err)
    bad = os.path.join(tmp, "bad.json")
    open(bad, "w").write("{nope")
    check("b. broken JSON -> error", kp.read(bad)[1].startswith("status file is not JSON"))
    lst = os.path.join(tmp, "list.json")
    open(lst, "w").write("[1, 2]")
    check("b. not an object -> error", kp.read(lst)[1] == "status file is not a JSON object")
    f = os.path.join(tmp, "s.json")
    json.dump({k: v for k, v in kp.SAMPLE.items() if k != "t"}, open(f, "w"))
    os.utime(f, (1793500000, 1793500000))
    p, err = kp.read(f)
    check("b. no 't' in the file -> the file's time", err is None and p["t"] == 1793500000, p and p["t"])
    big = os.path.join(tmp, "big.json")
    json.dump({**kp.SAMPLE, "trades": [{**kp.SAMPLE["trades"][0], "title": "x" * 150}] * 40,
               "positions": [{**kp.SAMPLE["positions"][0], "title": "y" * 150}] * 60}, open(big, "w"))
    old = kp.MAX_BYTES
    kp.MAX_BYTES = 8 * 1024
    try:
        p, err = kp.read(big)
    finally:
        kp.MAX_BYTES = old
    check("b. over the size limit -> trimmed (trades first) until it fits",
          err is None and len(json.dumps(p, separators=(",", ":"))) <= 8 * 1024 and len(p["trades"]) < 40, p and len(p["trades"]))


def git(*a, cwd=None):
    return subprocess.run(["git", *a], capture_output=True, text=True, cwd=cwd)


def part_c(tmp):
    remote = os.path.join(tmp, "remote.git")
    git("init", "-q", "--bare", remote)
    f = os.path.join(tmp, "status.json")
    json.dump(kp.SAMPLE, open(f, "w"))
    scratch = os.path.join(tmp, "scratch.git")
    r = kp.push_once(f, url=remote, git_dir=scratch)
    show = git("--git-dir", remote, "ls-tree", "--name-only", "kalshi")
    body = git("--git-dir", remote, "show", "kalshi:kalshi.json").stdout
    check("c. one push: the branch `kalshi` holds exactly kalshi.json", r.get("ok") and show.stdout.split() == ["kalshi.json"], (r, show.stdout, show.stderr))
    check("c. its content is the cleaned status (balance, positions)", json.loads(body or "{}").get("balance") == 512.34
          and len(json.loads(body or "{}").get("positions", [])) == 1, body[:200])
    json.dump({**kp.SAMPLE, "balance": 600}, open(f, "w"))
    r2 = kp.push_once(f, url=remote, git_dir=scratch)
    n = git("--git-dir", remote, "rev-list", "--count", "kalshi").stdout.strip()
    check("c. the next push replaces it (orphan commit, no history)", r2.get("ok") and n == "1"
          and json.loads(git("--git-dir", remote, "show", "kalshi:kalshi.json").stdout)["balance"] == 600, (r2, n))
    r3 = kp.push_once(os.path.join(tmp, "nope.json"), url=remote, git_dir=scratch)
    check("c. a missing status file pushes nothing", not r3["ok"] and "not found" in r3["error"], r3)
    r4 = lp.push({"t": 1}, remote, branch="live", git_dir=os.path.join(tmp, "live.git"))
    check("c. live.json's own push keeps its file name (file= defaults to live.json)",
          r4.get("ok") and git("--git-dir", remote, "ls-tree", "--name-only", "live").stdout.split() == ["live.json"], r4)


def part_d(tmp):
    f = os.path.join(tmp, "loop.json")
    calls, logs, t, rounds = [], [], [1000.0], [0]

    def fake_push(p, url, **kw):
        calls.append((p["balance"], kw.get("branch"), kw.get("file")))
        return {"ok": True, "commit": "abc"}

    def sleep(s):
        t[0] += s
        rounds[0] += 1
        if rounds[0] == 2:                                   # after round 2: the file shows up (pushed in round 3)
            json.dump(kp.SAMPLE, open(f, "w"))
        if rounds[0] == 4:                                   # after round 4: the Kalshi bot writes a new balance (round 5)
            json.dump({**kp.SAMPLE, "balance": 700}, open(f, "w"))
            os.utime(f, (t[0] + 5, t[0] + 5))
    kp.loop(f, every=60, keepalive=600, log=logs.append, clock=lambda: t[0], sleep=sleep, push_fn=fake_push, url="x",
            git_dir=os.path.join(tmp, "s.git"), max_rounds=16)
    check("d. waits while the status file is missing", logs[:2] == ["kalshi publish: waiting for the status file"] * 2, logs[:3])
    check("d. pushes on the file's first appearance and on a change, to branch kalshi as kalshi.json",
          calls[:2] == [(512.34, "kalshi", "kalshi.json"), (700.0, "kalshi", "kalshi.json")], calls)
    check("d. no push while unchanged, then a keep-alive push after 10 min", len(calls) == 3, calls)


# ================================================================================================ contract v2 + the kit
KIT = kp.kit
KIT_FILE = kp.KIT_PATH
NOW = 1793556000.0                       # Sun 2026-11-01 13:00 EST (18:00 UTC; EST since 06:00 UTC today)
MID = 1793505600.0                       # 00:00 ET Nov 1 (04:00 UTC: still EDT at midnight)


def iso(t, frac=""):
    import datetime as dt
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + frac + "Z"


def part_e():
    v1 = kp.clean(kp.SAMPLE, now=NOW)
    v2 = kp.clean(kp.SAMPLE_V2, now=NOW)
    check("e. v1 input -> v1 output (no strategies / equity keys, v 1)", v1["v"] == 1 and "strategies" not in v1 and "equity" not in v1, sorted(v1))
    check("e. v2 input -> v 2 with strategies and equity", v2["v"] == 2 and len(v2["strategies"]) == 2 and len(v2["equity"]) == 4
          and v2["strategies"][0] == {"name": "Weather", "mode": "live", "running": True, "today_pnl": 12.1, "total_pnl": 80.4,
                                      "trades": 41, "wins": 27, "losses": 14}, v2.get("strategies"))
    raw = {"strategies": [{"name": "S" * 99, "mode": "live", "running": 1, "trades": "7", "wins": 5.0, "losses": "2",
                           "today_pnl": "1.5", "total_pnl": None, "api_key": "zzz", "secret_sauce": "x"}] * 25 + [{"mode": "x"}, "junk"],
           "equity": [[1793500000 + i * 60, 50 + i * 0.01] for i in range(2000)] + [["bad", 1], {"t": 1793400000, "balance": "49"}]}
    c = kp.clean(raw, now=NOW)
    s0 = c["strategies"][0]
    check("e. strategies capped at 10, unknown keys dropped, names capped, counts as whole numbers",
          len(c["strategies"]) == 10 and set(s0) == {"name", "mode", "running", "today_pnl", "trades", "wins", "losses"}
          and len(s0["name"]) == 60 and s0["trades"] == 7 and isinstance(s0["trades"], int) and s0["running"] is True, s0)
    eq = c["equity"]
    check("e. equity: [unix, balance] pairs or {t, balance}, sorted, bad points dropped, downsampled to 500 (first and last kept)",
          len(eq) == 500 and eq[0] == [1793400000, 49.0] and eq[-1] == [1793500000 + 1999 * 60, round(50 + 1999 * 0.01, 4)]
          and all(eq[i][0] < eq[i + 1][0] for i in range(len(eq) - 1)), (len(eq), eq[:2], eq[-1:]))
    again = kp.clean(c, now=NOW + 5)
    check("e. clean() is idempotent (only pub_t moves)", {**again, "pub_t": 0} == {**c, "pub_t": 0})
    big = kp.clean({**kp.SAMPLE_V2, "equity": [[1793000000 + i, 1.0] for i in range(500)],
                    "trades": [{**kp.SAMPLE["trades"][0], "title": "x" * 150}] * 40}, now=NOW)
    fitted = KIT.fit(json.loads(json.dumps(big)), max_bytes=12 * 1024)
    check("e. fit(): over the limit trims trades, then days (keeps the newest), then positions, then equity, never loops",
          len(json.dumps(fitted, separators=(",", ":"))) <= 12 * 1024 and len(fitted["trades"]) < 40, len(json.dumps(fitted)))
    one = KIT.fit({"equity": [[1, 2.0]], "x": "y" * 500}, max_bytes=10)
    check("e. fit() gives up gracefully when nothing is left to trim", one["equity"] == [] and "x" in one, one)
    check("e. the kit's secret / path patterns are live_publish's", KIT._SECRET_KEY.pattern == lp._SECRET_KEY.pattern
          and KIT._PATHLIKE.pattern == lp._PATHLIKE.pattern)


def part_f():
    import datetime as dt
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    bad = []
    t = dt.datetime(2021, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    end = dt.datetime(2028, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    while t < end:                                       # every 61 min for 7 years: all DST switches, both directions
        if KIT.et_day(t) != dt.datetime.fromtimestamp(t, ny).date().isoformat():
            bad.append(t)
        t += 3660
    edges = [MID - 1, MID, MID + 1, 1793512799, 1793512800, 1793512801]     # Nov 1 midnight; 06:00 UTC switch to EST
    bad += [x for x in edges if KIT.et_day(x) != dt.datetime.fromtimestamp(x, ny).date().isoformat()]
    check("f. ET days without tzdata = zoneinfo America/New_York (2021-2027, DST edges, today's switch)", not bad, bad[:5])
    mids = [KIT.et_midnight(d) == dt.datetime.fromisoformat(d).replace(tzinfo=ny).timestamp()
            for d in ("2026-03-08", "2026-03-09", "2026-11-01", "2026-11-02", "2025-12-31", "2026-07-04")]
    check("f. et_midnight() on DST days", all(mids) and KIT.et_midnight("2026-11-01") == MID, mids)
    cases = {"KXETH15M-26NOV011215-15": "ETH up or down · 15 min to 12:15 PM ET Nov 1",
             "KXBTCD-26OCT2713-T80499.99": "Bitcoin above $80,500 at 1 PM ET Oct 27",
             "KXHYPE15M-26OCT310215-15": "HYPE up or down · 15 min to 2:15 AM ET Oct 31",
             "WEIRD": "WEIRD"}
    got = {k: KIT.ticker_title(k) for k in cases}
    check("f. plain titles from tickers, offline (spec examples)", got == cases, got)


# ------------------------------------------------------------------------------------------------ the bot's own files
def make_bot(root, extra_rows=()):
    """A bot folder like /home/ubuntu/kalshi (spec section 3 / 7): trades.db orders, account_truth, autotrader_status,
    autotune_state (eq_main 24 h), settings, plus a .env and keys/ that must never be read."""
    import sqlite3
    os.makedirs(os.path.join(root, "keys"), exist_ok=True)
    open(os.path.join(root, ".env"), "w").write("KALSHI_API_KEY_ID=ENVSECRET-0000\nKALSHI_PRIVATE_KEY_PATH=keys/k.pem\n")
    open(os.path.join(root, "keys", "k.pem"), "w").write("-----BEGIN PRIVATE KEY-----\nKEYSECRET\n-----END PRIVATE KEY-----\n")
    con = sqlite3.connect(os.path.join(root, "trades.db"))
    con.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, mode TEXT, signal_id INTEGER,
        ticker TEXT, asset TEXT, side TEXT, book_side TEXT, limit_price REAL, count REAL, client_order_id TEXT, order_id TEXT,
        filled REAL, avg_price REAL, fee REAL, status TEXT, error TEXT, close_ts REAL, result TEXT, pnl REAL,
        book TEXT DEFAULT 'main', sig_price REAL, UNIQUE(signal_id, mode))""")
    rows = [  # ts, mode, ticker, side, filled, avg_price, result, pnl, book
        (MID - 86400 * 9, "live", "KXETH15M-26OCT230915-15", "UP", 10, 0.96, "yes", 0.36, "main"),     # Oct 23: last week
        (MID - 86400 * 2, "live", "KXHYPE15M-26OCT310215-15", "UP", 18, 0.9683, "no", -17.47, None),     # Oct 30 (book NULL)
        (MID - 86400 * 2 + 600, "live", "KXETH15M-26OCT290230-30", "DOWN", 16, 0.81, "exit", -2.64, "exit"),
        (MID - 60, "live", "KXBTCD-26OCT3123-T80499.99", "up", 5, 0.95, "yes", 1.00, "latefav"),         # 23:59 ET Oct 31
        (MID + 60, "live", "KXETH15M-26NOV010015-15", "DOWN", 12, 0.95, "no", 2.00, "main"),            # 00:01 ET Nov 1
        (MID + 5400, "live", "KXBTC15M-26NOV010145-45", "YES", 4, 0.96, "yes", 0.16, "main"),            # 01:30 EDT
        (MID + 9000, "live", "KXGOLDD-26NOV0117-T4000", "NO", 3, 0.9, "no", 0.30, "gold"),               # 01:30 EST
        (NOW - 600, "live", "KXETH15M-26NOV011300-00", "DOWN", 7, 0.97, None, None, "main"),             # open bet
        (NOW - 500, "paper", "KXETH15M-26NOV011300-00", "UP", 9, 0.97, None, None, "sniper"),            # paper: never counted
        (NOW - 400, "live", "KXETH15M-26NOV011300-00", "UP", 0, None, None, None, "main"),               # missed: filled 0
    ] + list(extra_rows)
    for i, (ts, mode, tk, side, filled, avg, result, pnl, book) in enumerate(rows):
        asset = tk[2:].split("15M")[0].split("D-")[0].split("-")[0] if tk.startswith("KX") else None
        con.execute("INSERT INTO orders (ts, mode, signal_id, ticker, asset, side, count, filled, avg_price, result, pnl, book,"
                    " close_ts, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (ts, mode, i + 1, tk, asset, side, filled, filled, avg,
                                                                              result, pnl, book, ts + 900,
                                                                              "filled" if filled else "missed"))
    con.commit()
    con.close()
    json.dump({"ts": NOW - 4, "account": "main", "mode": "live", "problem": None, "value_mode": "off", "blocked": None,
               "balance": 41.09}, open(os.path.join(root, "autotrader_status.json"), "w"))
    json.dump({"total": 67.98, "cash": 61.19, "wallets": {"2": 61.19}, "open": [{}]}, open(os.path.join(root, "account_truth.json"), "w"))
    json.dump({"eq_main": [[int(NOW - 86400 + 900 * i), round(60 + i * 0.08, 2)] for i in range(96)], "guard_main": {}},
              open(os.path.join(root, "autotune_state.json"), "w"))
    json.dump({"MAIN_BOOK": 1, "HOURLY_BOOK": 0, "MAX_OPEN_TRADES": 2}, open(os.path.join(root, "bot_settings.json"), "w"))
    json.dump({"LATE_MODE": 2, "GOLD_MODE": 2, "FLIP_EXIT": 0}, open(os.path.join(root, "combo_settings.json"), "w"))
    json.dump({"SNIPER_LIVE": 0}, open(os.path.join(root, "sniper_settings.json"), "w"))
    return root


def part_g(tmp):
    bot = make_bot(os.path.join(tmp, "bot"))
    db = os.path.join(bot, "trades.db")
    before = (os.path.getmtime(db), open(db, "rb").read())
    p = KIT.bot_payload(bot, now=NOW, units=())
    check("g. bot files: today = SUM(pnl) since 00:00 ET (23:59 ET yesterday out; 00:01 EDT, 01:30 EDT and 01:30 EST in)",
          p["today_pnl"] == 2.46, p["today_pnl"])
    check("g. week from Monday 00:00 ET (Oct 23 out), total = every live graded row; paper and unfilled rows never count",
          p["week_pnl"] == round(-17.47 - 2.64 + 1.0 + 2.46, 2) and p["total_pnl"] == round(-17.47 - 2.64 + 1.0 + 2.46 + 0.36, 2),
          (p["week_pnl"], p["total_pnl"]))
    check("g. days by ET date of the order", p["days"] == [["2026-10-23", 0.36], ["2026-10-30", -20.11], ["2026-10-31", 1.0],
                                                          ["2026-11-01", 2.46]], p["days"])
    check("g. balance = account_truth total (cash + positions); live, running, plain status, real-money note",
          p["balance"] == 67.98 and p["mode"] == "live" and p["running"] is True and p["name"] == "Kalshi Edge v2"
          and p["status"] == "Trading · 3 live strategies · 1 open bet" and p["note"] == "Real money · main account", p)
    pos = p["positions"]
    check("g. open bets: live, filled, result NULL, not exit; DOWN -> no; cost as value; closes in ISO; asset and strategy",
          len(pos) == 1 and pos[0]["side"] == "no" and pos[0]["contracts"] == 7 and pos[0]["avg_price"] == 0.97
          and pos[0]["asset"] == "ETH" and pos[0]["strategy"] == "15-min favourites"
          and pos[0]["value"] == 6.79 and pos[0]["closes"] == iso(NOW + 300) and "pnl" not in pos[0]
          and pos[0]["title"] == "ETH up or down · 15 min to 1:00 PM ET Nov 1", pos)
    tr = p["trades"]
    check("g. trades newest first, UP/DOWN/up/YES/NO -> yes/no, exit -> sell, pnl null while open",
          [x["side"] for x in tr] == ["no", "no", "yes", "no", "yes", "no", "yes", "yes"]
          and tr[0].get("pnl") is None and [x["action"] for x in tr].count("sell") == 1 and tr[-1]["pnl"] == 0.36
          and [x["strategy"] for x in tr][:4] == ["15-min favourites", "Gold 5 PM", "15-min favourites", "15-min favourites"]
          and tr[1]["asset"] == "GOLD" and tr[2]["asset"] == "BTC", tr)
    st = {x["name"]: x for x in p["strategies"]}
    check("g. strategies per book (the three real-money ones first), wins / losses, modes from the settings files",
          [x["name"] for x in p["strategies"]][:3] == ["15-min favourites", "Late favourite (BTC hourly)", "Gold 5 PM"]
          and st["15-min favourites"]["total_pnl"] == round(0.36 - 17.47 + 2.0 + 0.16, 2) and st["15-min favourites"]["wins"] == 3
          and st["15-min favourites"]["losses"] == 1 and st["15-min favourites"]["today_pnl"] == 2.16
          and st["Gold 5 PM"]["mode"] == "live" and st["Flip exit sell-backs"]["mode"] == "off"
          and st["Flip exit sell-backs"]["running"] is False, p["strategies"])
    eq = p["equity"]
    check("g. equity: eq_main (24 h) then the balance now", len(eq) == 97 and eq[-1] == [int(NOW), 67.98] and eq[0][1] == 60.0, eq[-2:])
    check("g. trades.db untouched (opened read-only)", (os.path.getmtime(db), open(db, "rb").read()) == before)
    open(os.path.join(bot, "paused.txt"), "w").write(str(int(NOW + 3600)))
    pp = KIT.bot_payload(bot, now=NOW, units=())
    open(os.path.join(bot, "paused.txt"), "w").write("0")
    p0 = KIT.bot_payload(bot, now=NOW, units=())
    open(os.path.join(bot, "paused.txt"), "w").write(str(int(NOW - 60)))
    pold = KIT.bot_payload(bot, now=NOW, units=())
    os.remove(os.path.join(bot, "paused.txt"))
    json.dump({"ts": NOW - 1500, "mode": "live"}, open(os.path.join(bot, "autotrader_status.json"), "w"))
    quiet = KIT.bot_payload(bot, now=NOW, units=())
    json.dump({"ts": NOW - 600, "mode": "live", "blocked": "15-min book off (MAIN_BOOK 0)"}, open(os.path.join(bot, "autotrader_status.json"), "w"))
    ps = KIT.bot_payload(bot, now=NOW, units=())
    check("g. paused.txt: 'Paused until <ET time>' / 'Paused' (0), a run-out pause ignored; blocked text; a silent trader",
          pp["running"] is False and pp["status"] == "Paused until Nov 1, 2:00 PM ET" and ps["running"] is False
          and ps["status"] == "15-min book off (MAIN_BOOK 0)" and quiet["running"] is False
          and quiet["status"] == "No word from the trader for 25 min" and p0["status"] == "Paused" and p0["running"] is False
          and pold["running"] is True and pold["status"].startswith("Trading"), (pp["status"], ps["status"], quiet["status"],
                                                                                p0["status"], pold["status"]))
    empty = KIT.bot_payload(os.path.join(tmp, "nothing-here"), now=NOW, units=())
    check("g. a missing bot folder gives a calm card, not a crash", empty["kind"] == "kalshi" and empty["running"] is False
          and "trades.db could not be read" in empty["status"] and empty["positions"] == [], empty["status"])
    # what it opens: an audit hook in a child process records every file the reader opens
    probe = os.path.join(tmp, "probe.py")
    open(probe, "w").write(
        "import sys, json, importlib.util\n"
        "seen = []\n"
        "sys.addaudithook(lambda ev, a: seen.append(str(a[0])) if ev in ('open', 'sqlite3.connect') and a else None)\n"
        f"spec = importlib.util.spec_from_file_location('k', {KIT_FILE!r}); k = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(k)\nseen.clear()\n"
        f"p = k.bot_payload({bot!r}, now={NOW!r}, units=())\n"
        "print(json.dumps(seen))\n")
    r = subprocess.run([sys.executable, "-I", "-B", probe], capture_output=True, text=True, timeout=60)
    seen = json.loads((r.stdout or "[]").strip().splitlines()[-1]) if r.returncode == 0 else ["<probe failed>", r.stderr[-300:]]
    check("g. reads only the money / status / settings files: never .env, keys/, sniper.db or the bot's code",
          seen and not [x for x in seen if ".env" in x or os.sep + "keys" in x or "sniper.db" in x or x.endswith(".py")]
          and any(x.endswith("trades.db") or "trades.db" in x for x in seen), seen)


# ------------------------------------------------------------------------------------------------ a mock Kalshi API
class MockKalshi:
    """Kalshi's trade API on 127.0.0.1, verifying every request's signature with the test key's PUBLIC half."""

    def __init__(self, pub, key_id, data):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        self.pub, self.key_id, self.data, self.log, self.mode = pub, key_id, data, [], {}
        me = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, headers=()):
                b = json.dumps(body).encode()
                self.send_response(code)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _other(self):
                me.log.append((self.command, self.path, False))
                self._send(405, {"error": "method not allowed"})
            do_POST = do_PUT = do_DELETE = do_PATCH = _other

            def do_GET(self):
                path, _, query = self.path.partition("?")
                ok = me.verify(self.headers, "GET", path)
                me.log.append(("GET", self.path, ok))
                if not ok:
                    return self._send(401, {"code": "unauthorized", "message": f"bad signature for {me.key_id}"})
                q = dict(x.split("=", 1) for x in query.split("&") if "=" in x)
                p = path[len("/trade-api/v2"):]
                if me.mode.get("redirect"):
                    return self._send(302, {}, [("Location", "http://127.0.0.1:9/steal")])
                if p == "/portfolio/balance":
                    if me.mode.get("429"):
                        return self._send(429, {"error": "too many requests"})
                    return self._send(200, me.data["balance"])
                if p == "/portfolio/positions":
                    return self._send(200, {"market_positions": me.data["positions"], "event_positions": [], "cursor": ""})
                if p == "/portfolio/fills":
                    f = me.data["fills"]
                    return self._send(200, {"fills": f[2:], "cursor": ""} if q.get("cursor") == "page2" else {"fills": f[:2], "cursor": "page2"})
                if p == "/portfolio/settlements":
                    return self._send(200, {"settlements": me.data["settlements"], "cursor": None})
                if p.startswith("/markets/") and p[9:] in me.data["markets"]:
                    return self._send(200, {"market": me.data["markets"][p[9:]]})
                return self._send(404, {"code": "not_found"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}/trade-api/v2"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def verify(self, headers, method, path):
        import base64
        import time as _t
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ed25519, padding
        try:
            ts = headers.get("KALSHI-ACCESS-TIMESTAMP") or ""
            if headers.get("KALSHI-ACCESS-KEY") != self.key_id or abs(int(ts) - _t.time() * 1000) > 60_000:
                return False
            sig = base64.b64decode(headers.get("KALSHI-ACCESS-SIGNATURE") or "")
            msg = (ts + method + path.split("?")[0]).encode()
            if isinstance(self.pub, ed25519.Ed25519PublicKey):
                self.pub.verify(sig, msg)
            else:
                self.pub.verify(sig, msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
            return True
        except Exception:
            return False

    def close(self):
        self.httpd.shutdown()


def api_data():
    A, B, C, D, E = "KXA-26NOV01", "KXB-26OCT30", "KXC-26NOV02", "KXD-26OCT26", "KXE-26OCT20"
    fills = [
        {"fill_id": "fC1", "trade_id": "fC1", "ticker": C, "market_ticker": C, "outcome_side": "yes", "book_side": "bid",
         "count_fp": "4.00", "yes_price_dollars": "0.5500", "no_price_dollars": "0.4500", "fee_cost": "0.0400",
         "created_time": iso(NOW - 3 * 3600, ".123456789")},                                  # Nov 1 10:00 ET, still open
        {"fill_id": "fA1", "ticker": A, "outcome_side": "yes", "book_side": "bid", "count_fp": "10.00",
         "yes_price_dollars": "0.4000", "no_price_dollars": "0.6000", "fee_cost": "0.1000", "created_time": iso(MID - 60)},
        {"fill_id": "fB2", "ticker": B, "outcome_side": "yes", "book_side": "bid", "count_fp": "5.00",
         "yes_price_dollars": "0.5000", "no_price_dollars": "0.5000", "fee_cost": "0.0500",
         "created_time": iso(MID - 2 * 86400 + 15 * 3600 + 3600 * 0)},                          # Oct 30 15:00 ET: sells the NO
        {"fill_id": "fB1", "ticker": B, "outcome_side": "no", "book_side": "ask", "count_fp": "5.00",
         "yes_price_dollars": "0.7000", "no_price_dollars": "0.3000", "fee_cost": "0.0500",
         "created_time": iso(MID - 2 * 86400 + 12 * 3600)},                                     # Oct 30 12:00 ET: buys NO at 30c
        {"trade_id": "fD1", "ticker": D, "side": "yes", "action": "buy", "count": 2, "yes_price": 20, "no_price": 80,
         "created_time": iso(MID - 6 * 86400 + 9 * 3600)},                                      # legacy cents fields (Mon Oct 26)
        {"fill_id": "fE1", "ticker": E, "outcome_side": "yes", "count_fp": "1.00", "yes_price_dollars": "0.9000",
         "no_price_dollars": "0.1000", "fee_cost": "0.0100", "created_time": iso(MID - 12 * 86400 + 10 * 3600)},
    ]
    settlements = [
        {"ticker": A, "event_ticker": "KXA", "market_result": "yes", "yes_count_fp": "10.00", "yes_total_cost_dollars": "4.0000",
         "no_count_fp": "0.00", "no_total_cost_dollars": "0.0000", "revenue": 1000, "settled_time": iso(MID + 60),
         "fee_cost": "0.1000", "value": 100},                                                   # 00:01 ET Nov 1
        {"ticker": B, "market_result": "no", "yes_count_fp": "0.00", "no_count_fp": "0.00", "revenue": 0,
         "yes_total_cost_dollars": "0", "no_total_cost_dollars": "0", "settled_time": iso(MID - 2 * 86400 + 20 * 3600), "fee_cost": "0"},
        {"ticker": D, "market_result": "no", "yes_count": 2, "no_count": 0, "yes_total_cost": 40, "no_total_cost": 0,
         "revenue": 0, "settled_time": iso(MID - 6 * 86400 + 18 * 3600)},
        {"ticker": E, "market_result": "yes", "yes_count_fp": "1.00", "no_count_fp": "0.00", "yes_total_cost_dollars": "0.9000",
         "no_total_cost_dollars": "0", "revenue": 100, "value": 100, "settled_time": iso(MID - 12 * 86400 + 16 * 3600), "fee_cost": "0.01"},
    ]
    markets = {C: {"ticker": C, "title": "Will C happen?", "yes_sub_title": "Above 5", "status": "active", "yes_bid_dollars": "0.6000",
                   "yes_ask_dollars": "0.6200", "no_bid_dollars": "0.3800", "last_price_dollars": "0.6100", "close_time": "2026-11-02T21:00:00Z"},
               A: {"ticker": A, "title": "Will A happen?", "status": "finalized", "result": "yes"},
               B: {"ticker": B, "title": "Will B happen?", "status": "finalized", "result": "no"},
               D: {"ticker": D, "title": "Will D happen?", "status": "finalized", "result": "no"}}
    return {"balance": {"balance": 10000, "balance_dollars": "100.0000", "portfolio_value": 240, "updated_ts": int(NOW - 60)},
            "positions": [{"ticker": C, "position_fp": "4.00", "market_exposure_dollars": "2.2000", "realized_pnl_dollars": "0.0000",
                           "fees_paid_dollars": "0.0400", "total_traded_dollars": "2.2000", "last_updated_ts": iso(NOW - 3 * 3600)}],
            "fills": fills, "settlements": settlements, "markets": markets}


def make_keys(tmp):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
    out = {}
    for name, key in (("rsa", rsa.generate_private_key(public_exponent=65537, key_size=2048)),
                      ("ed25519", ed25519.Ed25519PrivateKey.generate())):
        fmt = serialization.PrivateFormat.TraditionalOpenSSL if name == "rsa" else serialization.PrivateFormat.PKCS8
        path = os.path.join(tmp, f"test-{name}-DO-NOT-LEAK.pem")
        with open(path, "wb") as fh:
            fh.write(key.private_bytes(serialization.Encoding.PEM, fmt, serialization.NoEncryption()))
        out[name] = (path, key.public_key())
    return out


KEY_ID = "TESTKEY-1234-abcd-SECRET"


def part_h(tmp, keys):
    rsa_path, rsa_pub = keys["rsa"]
    srv = MockKalshi(rsa_pub, KEY_ID, api_data())
    try:
        st = {"key_id": KEY_ID, "key_ref": rsa_path, "base": srv.base}
        client = KIT.make_client(st)
        p = kp.api_payload(client, now=NOW, name="Kalshi bot")
        gets = [x for x in srv.log if x[0] == "GET"]
        check("h. RSA-PSS: every request reached the mock signed and verified (timestamp + GET + path, no query)",
              len(srv.log) == len(gets) == 10 and all(x[2] for x in srv.log), srv.log)
        check("h. P&L by ET day: a 23:59 ET buy settled at 00:01 ET books on the settlement day; NO buy/sell, legacy cents",
              p["days"] == [["2026-10-20", 0.09], ["2026-10-26", -0.4], ["2026-10-30", 0.9], ["2026-11-01", 6.06]], p["days"])
        check("h. today = realized today + open P&L (bid, net of fees); week from Monday; total; balance = cash + portfolio",
              (p["today_pnl"], p["week_pnl"], p["total_pnl"], p["balance"]) == (6.06, 6.56, 6.65, 102.4),
              (p["today_pnl"], p["week_pnl"], p["total_pnl"], p["balance"]))
        check("h. open position: side, contracts, avg price, bid price, value, pnl net of fees, closes, title + subtitle",
              p["positions"] == [{"ticker": "KXC-26NOV02", "title": "Will C happen? · Above 5", "side": "yes", "contracts": 4.0,
                                  "avg_price": 0.55, "price": 0.6, "value": 2.4, "pnl": 0.16, "closes": "2026-11-02T21:00:00Z"}],
              p["positions"])
        lab = [(x["ticker"][:3], x["action"], x["side"], x["price"], x.get("pnl")) for x in p["trades"]]
        check("h. trades from fills + settlements, newest first: buy/sell yes/no from outcome_side, the side's price",
              lab == [("KXC", "buy", "yes", 0.55, None), ("KXA", "settled", "yes", 1.0, 5.9), ("KXA", "buy", "yes", 0.4, None),
                      ("KXB", "sell", "no", 0.5, 0.9), ("KXB", "buy", "no", 0.3, None), ("KXD", "settled", "yes", 0.0, -0.4),
                      ("KXD", "buy", "yes", 0.2, None), ("KXE", "settled", "yes", 1.0, 0.09), ("KXE", "buy", "yes", 0.9, None)], lab)
        eqv = [x[1] for x in p["equity"]]
        check("h. equity: the balance now walked back through the days", eqv == [95.84, 95.44, 96.34, 102.4]
              and p["equity"][-1][0] == int(NOW) and all(p["equity"][i][0] < p["equity"][i + 1][0] for i in range(3)), p["equity"])
        check("h. live mode, plain status and note, unknown market (404) keeps its ticker as title",
              p["mode"] == "live" and p["status"] == "1 open position · cash $100.00" and p["note"] == "Last fill Nov 1, 10:00 AM ET"
              and any(x["title"] == "KXE-26OCT20" for x in p["trades"]), (p["status"], p["note"]))
        s = json.dumps(p)
        check("h. the key id and key path never reach the payload", KEY_ID not in s and "DO-NOT-LEAK" not in s)
        cache = {}
        n0 = len(srv.log)
        kp.api_payload(client, now=NOW, cache=cache)
        n1 = len(srv.log)
        kp.api_payload(client, now=NOW, cache=cache)
        check("h. loop rounds are cheap: titles cached, fills / settlements from just before the newest one",
              n1 - n0 == 10 and len(srv.log) - n1 == 6 and any("min_ts=" in x[1] for x in srv.log[n1:])
              and [x[1] for x in srv.log[n1:] if "/markets/" in x[1]] == ["/trade-api/v2/markets/KXC-26NOV02"], srv.log[n1:])
        ed_path, ed_pub = keys["ed25519"]
        srv2 = MockKalshi(ed_pub, KEY_ID, api_data())
        try:
            p2 = kp.api_payload(KIT.make_client({"key_id": KEY_ID, "key_ref": ed_path, "base": srv2.base}), now=NOW)
            check("h. Ed25519 keys sign too (same numbers)", all(x[2] for x in srv2.log) and p2["days"] == p["days"], srv2.log[:2])
        finally:
            srv2.close()
        srv.mode["429"] = True
        n = len(srv.log)
        try:
            kp.api_payload(KIT.make_client(st), now=NOW)
            err = ""
        except kp.ApiError as e:
            err = str(e)
        check("h. HTTP 429: stops at once (no retry storm), says so", "429" in err and len(srv.log) - n == 1, (err, srv.log[n:]))
        srv.mode = {"redirect": True}
        try:
            KIT.make_client(st).get("/portfolio/balance")
            red = "followed"
        except kp.ReadOnlyError as e:
            red = str(e)
        check("h. a redirect is refused (the signed request never leaves Kalshi's API)", "redirect" in red, red)
    finally:
        srv.close()
    return srv


def part_i(tmp, keys):
    rsa_path, rsa_pub = keys["rsa"]
    srv = MockKalshi(rsa_pub, KEY_ID, api_data())
    try:
        c = KIT.make_client({"key_id": KEY_ID, "key_ref": rsa_path, "base": srv.base})
        refused = []
        for m, path in (("POST", "/portfolio/balance"), ("DELETE", "/portfolio/orders"), ("PUT", "/portfolio/positions"),
                        ("get", "/portfolio/balance"), ("GET", "/portfolio/orders"), ("GET", "/portfolio/events/orders"),
                        ("GET", "/markets/KXA/orderbook"), ("GET", "/portfolio/balance?x=1"), ("GET", "/markets/../portfolio/orders"),
                        ("GET", "/api_keys"), ("GET", "/markets/KX A"), ("GET", "//portfolio/balance")):
            try:
                c.request(m, path)
            except kp.ReadOnlyError:
                refused.append((m, path))
        check("i. GET-only: POST / DELETE / PUT / orders / api_keys / odd paths are refused before any request",
              len(refused) == 12 and srv.log == [], (refused, srv.log))
        bases = ("https://evil.example.com/trade-api/v2", "http://external-api.kalshi.com/trade-api/v2",
                 "https://external-api.kalshi.com/trade-api/v2/../v1", "https://user:pw@external-api.kalshi.com/trade-api/v2",
                 "https://external-api.kalshi.com.evil.com/trade-api/v2", "https://external-api.kalshi.com:8443/trade-api/v2")
        bad = []
        for b in bases:
            try:
                KIT.check_base(b)
                bad.append(b)
            except kp.ReadOnlyError:
                pass
        good = [KIT.check_base(b) for b in (KIT.PROD_BASE, KIT.DEMO_BASE, "https://api.elections.kalshi.com/trade-api/v2/")]
        check("i. only Kalshi's API (or a loopback test server) can be the base URL", not bad and len(good) == 3, bad)
    finally:
        srv.close()


def part_j(tmp, keys):
    rsa_path, rsa_pub = keys["rsa"]
    missing = os.path.join(tmp, "Users", "me", "kalshi-SECRET-PATH.pem")
    msgs = []
    for st in ({"key_id": KEY_ID, "key_ref": missing, "base": KIT.PROD_BASE},
               {"key_id": KEY_ID, "key_ref": "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----", "base": KIT.PROD_BASE}):
        try:
            KIT.make_client(st)
        except kp.ApiError as e:
            msgs.append(str(e))
    check("j. a bad key file / PEM: the error names neither the path nor the key id nor the PEM",
          len(msgs) == 2 and not any(KEY_ID in m or "SECRET-PATH" in m or "AAAA" in m for m in msgs), msgs)
    srv = MockKalshi(rsa_pub, "SOME-OTHER-KEY", api_data())          # the server echoes the key id it expects; ours fails
    try:
        try:
            KIT.make_client({"key_id": KEY_ID, "key_ref": rsa_path, "base": srv.base}).get("/portfolio/balance")
            e401 = ""
        except kp.ApiError as e:
            e401 = str(e)
    finally:
        srv.close()
    check("j. HTTP 401 error text is shown without the key id", "401" in e401 and KEY_ID not in e401, e401)
    red = KIT.redact(f"KALSHI-ACCESS-KEY: {KEY_ID} KALSHI-ACCESS-SIGNATURE: {'Q' * 344} key at C:\\Users\\me\\k.pem "
                     f"ssh ubuntu@10.20.30.40 failed", (KEY_ID,))
    check("j. redact(): key id, signature, Windows paths and IP addresses", KEY_ID not in red and "QQQQ" not in red
          and "Users" not in red and "10.20.30.40" not in red, red)
    logf = os.path.join(tmp, "k.log")
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        KIT.Log(logf, (KEY_ID,))(f"failed with {KEY_ID}")
    check("j. the log file never holds the key id", KEY_ID not in open(logf).read())


def run(args, cwd=None, env=None, timeout=120):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("KALSHI", "LE_"))}
    e.update(env or {}, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=cwd, env=e, timeout=timeout)


def part_k(tmp, keys):
    """The standalone file, copied far from the repo, and the module give the same JSON for the same input."""
    alone = os.path.join(tmp, "elsewhere")
    os.makedirs(alone)
    copy = os.path.join(alone, "kalshi_status_vm.py")
    shutil.copy(KIT_FILE, copy)
    home = {"KALSHI_JARVIS_HOME": os.path.join(tmp, "home")}
    rsa_path, rsa_pub = keys["rsa"]
    srv = MockKalshi(rsa_pub, KEY_ID, api_data())
    bot = make_bot(os.path.join(tmp, "bot_k"))
    statf = os.path.join(tmp, "status.json")
    json.dump({**kp.SAMPLE_V2, "api_key": "nope"}, open(statf, "w"))
    try:
        common = ["--check", "--now", str(NOW)]
        pairs = {"api": ["--from-api", "--base", srv.base, "--key-id", KEY_ID, "--key-file", rsa_path],
                 "bot": ["--from-bot", bot, "--units", "none"], "src": ["--src", statf]}
        for name, args in pairs.items():
            a = run(["-I", copy, *args, *common], cwd=alone, env=home)
            b = run(["-m", "engine.kalshi_publish", *args, *common], cwd=ROOT, env=home)
            try:
                ja, jb = json.loads(a.stdout), json.loads(b.stdout)
            except ValueError:
                ja, jb = {"err": a.stdout[-300:] + a.stderr[-300:]}, {"err": b.stdout[-300:] + b.stderr[-300:]}
            check(f"k. same JSON from the standalone copy (python -I, outside the repo) and the module: --{name if name != 'bot' else 'from-bot'}",
                  ja == jb and ja.get("kind") == "kalshi" and "err" not in ja, (ja, jb) if ja != jb else ja.get("err"))
        a = run(["-I", copy, "--from-api", "--base", srv.base, "--key-id", KEY_ID, "--key-file", rsa_path, "--check", "--now", str(NOW)],
                cwd=alone, env=home)
        check("k. the key id / path never in the output", KEY_ID not in a.stdout + a.stderr and "DO-NOT-LEAK" not in a.stdout + a.stderr)
        r = run(["-I", copy, "--from-api", "--check"], cwd=alone, env=home)
        check("k. API mode is off unless asked, and without a key it says how to give one (exit 1)", r.returncode == 1
              and "no Kalshi API key" in r.stdout, r.stdout[-200:])
        r = run(["-I", copy, "--check"], cwd=alone, env=home)
        check("k. no source -> exit 2 with a hint", r.returncode == 2 and "--from-bot" in r.stdout)
    finally:
        srv.close()


def part_l(tmp):
    """--ssh / --from-vm: the file is sent to the 'VM' inside one shell line through a fake srv.py (same code as the
    PC's: python srv.py x.sh -> run the command, print its output with \\r\\r\\n line ends)."""
    bot = make_bot(os.path.join(tmp, "vm", "kalshi"))
    helper_dir = os.path.join(tmp, "scratch")
    os.makedirs(os.path.join(helper_dir, "cloud_linux"))
    open(os.path.join(helper_dir, "cloud_linux", "deploy_to_oracle.py"), "w").write("# stand-in\n")
    srv_py = os.path.join(helper_dir, "srv.py")
    open(srv_py, "w").write(
        "import subprocess, sys\n"
        "cmd = open(sys.argv[1]).read()\n"
        "r = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)\n"
        "print(('Welcome to the VM\\n' + r.stdout + r.stderr).replace('\\n', '\\r\\r\\n'))\n")
    home = {"KALSHI_JARVIS_HOME": os.path.join(tmp, "home_l")}
    a = run(["-m", "engine.kalshi_publish", "--ssh", "--vm-helper", srv_py, "--vm-dir", bot, "--units", "none", "--check",
             "--now", str(NOW)], cwd=ROOT, env=home)
    b = run(["-m", "engine.kalshi_publish", "--from-bot", bot, "--units", "none", "--check", "--now", str(NOW)], cwd=ROOT, env=home)
    try:
        ja, jb = json.loads(a.stdout), json.loads(b.stdout)
    except ValueError:
        ja, jb = {"err": (a.stdout + a.stderr)[-400:]}, {}
    check("l. --ssh through srv.py gives the same payload as reading the files directly", ja == jb and ja.get("today_pnl") == 2.46,
          ja.get("err") or (ja, jb))
    sh = open(os.path.join(tmp, "home_l", "vm_read.sh"), "rb").read()
    check("l. the VM command is one ASCII shell line: cd, nice'd isolated python (-I), the file inside, under 100 KB",
          sh.count(b"\n") == 1 and b"nice -n 15 ionice -c3" in sh and b'"$PY" -I -c' in sh and b"--from-bot . --emit" in sh
          and sh.isascii() and len(sh) < 100_000, sh[:120])
    check("l. markers survive the \\r\\r\\n line ends", KIT.parse_emit("x\r\r\n" + KIT.MARK_A + '{"a":\r\r\n1}' + KIT.MARK_B) == {"a": 1})
    r = run(["-m", "engine.kalshi_publish", "--ssh", "--vm-helper", os.path.join(tmp, "nope", "srv.py"), "--check"], cwd=ROOT, env=home)
    check("l. no srv.py -> a plain error (exit 1)", r.returncode == 1 and "srv.py" in r.stdout, r.stdout[-200:])
    found = KIT.find_vm_helper(appdata=os.path.join(tmp, "appdata"))
    deep = os.path.join(tmp, "appdata", "Claude", "scratch-workspaces", "g1", "g2", "scratch-2026-01-01-000000")
    os.makedirs(os.path.join(deep, "cloud_linux"))
    shutil.copy(srv_py, deep)
    open(os.path.join(deep, "cloud_linux", "deploy_to_oracle.py"), "w").write("#\n")
    check("l. srv.py is found under %APPDATA%\\Claude\\scratch-workspaces", found is None
          and KIT.find_vm_helper(appdata=os.path.join(tmp, "appdata")) == os.path.join(deep, "srv.py"))


def part_m(tmp):
    remote = os.path.join(tmp, "remote_m.git")
    git("init", "-q", "--bare", remote)
    p = kp.clean(kp.SAMPLE_V2, now=NOW)
    r = KIT.push(p, remote, git_dir=os.path.join(tmp, "kit_scratch.git"))
    body = git("--git-dir", remote, "show", "kalshi:kalshi.json").stdout
    check("m. the kit's own push: one orphan commit on `kalshi` holding exactly kalshi.json",
          r.get("ok") and git("--git-dir", remote, "ls-tree", "--name-only", "kalshi").stdout.split() == ["kalshi.json"]
          and json.loads(body or "{}") == p, r)
    statf = os.path.join(tmp, "cron_status.json")
    json.dump(kp.SAMPLE_V2, open(statf, "w"))
    home = {"KALSHI_JARVIS_HOME": os.path.join(tmp, "home_m")}
    args = ["-I", KIT_FILE, "--src", statf, "--cron", "--repo", remote, "--git-dir", os.path.join(tmp, "cron.git")]
    c1 = run(args, env=home)
    h1 = git("--git-dir", remote, "rev-parse", "kalshi").stdout.strip()
    c2 = run(args, env=home)
    h2 = git("--git-dir", remote, "rev-parse", "kalshi").stdout.strip()
    json.dump({**kp.SAMPLE_V2, "balance": 70.12}, open(statf, "w"))
    c3 = run(args, env=home)
    h3 = git("--git-dir", remote, "rev-parse", "kalshi").stdout.strip()
    check("m. --cron: pushes, stays quiet while nothing changed, pushes again on a change",
          (c1.returncode, c2.returncode, c3.returncode) == (0, 0, 0) and bool(h1) and h1 == h2 and h2 != h3 and c2.stdout == ""
          and json.loads(git("--git-dir", remote, "show", "kalshi:kalshi.json").stdout)["balance"] == 70.12,
          (c1.stdout + c1.stderr, c2.stdout, h1, h2, h3))
    r = run(["-m", "engine.kalshi_publish", "--from-bot", make_bot(os.path.join(tmp, "bot_m")), "--units", "none", "--once",
             "--repo", remote, "--git-dir", os.path.join(tmp, "mod.git"), "--now", str(NOW)], cwd=ROOT, env=home)
    got = json.loads(git("--git-dir", remote, "show", "kalshi:kalshi.json").stdout or "{}")
    check("m. the module's push (data/kalshi_pub.git route, the repo's git login) sends the same payload",
          r.returncode == 0 and got.get("name") == "Kalshi Edge v2" and got.get("today_pnl") == 2.46
          and git("--git-dir", remote, "rev-list", "--count", "kalshi").stdout.strip() == "1", (r.stdout + r.stderr)[-300:])
    import time as _time
    bot2 = make_bot(os.path.join(tmp, "bot_m2"))
    json.dump({"ts": _time.time(), "mode": "live"}, open(os.path.join(bot2, "autotrader_status.json"), "w"))
    remote2, gd = os.path.join(tmp, "remote_m2.git"), os.path.join(tmp, "cron2.git")
    git("init", "-q", "--bare", remote2)
    argsb = ["-I", KIT_FILE, "--from-bot", bot2, "--units", "none", "--cron", "--repo", remote2, "--git-dir", gd]
    b1 = run(argsb, env=home)
    r1 = git("--git-dir", remote2, "rev-parse", "kalshi").stdout.strip()
    b2 = run(argsb, env=home)
    r2 = git("--git-dir", remote2, "rev-parse", "kalshi").stdout.strip()
    check("m. --cron on the live clock: the second minute is quiet (clocks and the equity point's time don't count as a change)",
          b1.returncode == 0 and b2.returncode == 0 and r1 and r1 == r2 and b2.stdout == "", (b1.stdout + b1.stderr, b2.stdout))

    def loose():
        out = git("--git-dir", gd, "count-objects", "-v").stdout
        return int(next((ln.split()[1] for ln in out.splitlines() if ln.startswith("count:")), "0"))
    st = json.load(open(gd + ".last.json"))
    for bal in (70.1, 70.2):                                   # two more changed pushes: old commits pile up as loose objects
        json.dump({"total": bal}, open(os.path.join(bot2, "account_truth.json"), "w"))
        run(argsb, env=home)
    before = loose()
    json.dump({**json.load(open(gd + ".last.json")), "n": 29}, open(gd + ".last.json", "w"))
    json.dump({"total": 70.3}, open(os.path.join(bot2, "account_truth.json"), "w"))
    b3 = run(argsb, env=home)
    after = loose()
    n_now = json.load(open(gd + ".last.json")).get("n")
    check("m. --cron counts its pushes across runs and prunes the scratch repo every 30th (no pile-up on the server)",
          st.get("n") == 1 and n_now == 30 and b3.returncode == 0 and after < before
          and json.loads(git("--git-dir", remote2, "show", "kalshi:kalshi.json").stdout)["balance"] == 70.3, (st, n_now, before, after))
    env = KIT.push_env("/home/ubuntu/kalshi_jarvis/deploy_key")
    check("m. --deploy-key: git pushes over SSH with only that key (and the SSH repo URL)",
          "-i /home/ubuntu/kalshi_jarvis/deploy_key" in env.get("GIT_SSH_COMMAND", "") and "IdentitiesOnly=yes" in env["GIT_SSH_COMMAND"]
          and KIT.phone_url(KIT.REPO_SSH) == "https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/kalshi/kalshi.json")


def part_n():
    """The public kit: nothing secret or private in it."""
    import re as _re
    pub = os.path.dirname(KIT_FILE)
    kit_dir = os.path.dirname(pub)
    names = sorted(n for n in os.listdir(pub) if os.path.isfile(os.path.join(pub, n)))
    texts = {n: open(os.path.join(pub, n), encoding="utf-8").read() for n in names}
    leaks = []
    for n, t in texts.items():
        for pat in (r"trycloudflare\.com/[A-Za-z0-9]", r"-----BEGIN [A-Z ]*PRIVATE KEY-----\s*\n[A-Za-z0-9+/]{20,}",
                    r"Demetri", r"scratch-workspaces\\[0-9a-f]{8}-"):
            if _re.search(pat, t):
                leaks.append((n, pat))
        ips = set(_re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", t)) - {"127.0.0.1", "0.0.0.0"}
        if ips:
            leaks.append((n, sorted(ips)))
    check("n. public kit files: no IP address but loopback, no tunnel URL, private key, owner name or private folder ids",
          not leaks, leaks)
    bad = [os.path.join(d, f) for d, _, fs in os.walk(kit_dir) for f in fs if f.endswith((".pem", ".key")) or f.startswith(".env")]
    check("n. no key files in the kit", not bad, bad)
    check("n. public/ holds the VM entry and its SETUP.md", {"kalshi_status_vm.py", "SETUP.md"} <= set(names), names)



def main():
    tmp = tempfile.mkdtemp(prefix="le_kalshi_")
    try:
        part_a()
        part_b(tmp)
        part_c(tmp)
        part_d(tmp)
        part_e()
        part_f()
        part_g(tmp)
        keys = make_keys(tmp)
        part_h(tmp, keys)
        part_i(tmp, keys)
        part_j(tmp, keys)
        part_k(tmp, keys)
        part_l(tmp)
        part_m(tmp)
        part_n()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nkalshi publish: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
