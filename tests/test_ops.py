"""Owner's PC helpers (engine/ops_checks.py + the double-click .bat files): health checks with their one fix, friendly
error translation, the phone notices (pre-session, day / week summary, internet / NinjaTrader drop + recovery, MFFU
inactivity, eval passed / failed, contract roll), sending each once, nightly backup + log rotation, the update guard,
the heartbeat's "ops" block + logs/heartbeat_last.json, push.pc_send_now, the cloud README row, and static checks of
UPDATE.bat / START_DASHBOARD.bat / HEALTH_CHECK.bat / STOP_BOT.bat / SETUP_SHORTCUTS.bat and their PowerShell scripts
(PowerShell can't run here: they are parsed and grepped). No network, nothing written under data/ or logs/.

  python -X utf8 -m tests.test_ops
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from types import SimpleNamespace

from engine import heartbeat, ops_checks as oc, push
from engine.tradovate import LIVE_PHRASE

ET = oc.ET
ROOT = oc.ROOT
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def ts(y, mo, d, h=0, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()


def nt_tree(base, conn="CONNECTED", bar_t=None, open_t=None):
    f = os.path.join(base, "NinjaTrader 8")
    for d in ("incoming", "outgoing", "le_feed"):
        os.makedirs(os.path.join(f, d), exist_ok=True)
    if conn:
        with open(os.path.join(f, "outgoing", "MFFU Rithmic.txt"), "w") as fh:
            fh.write(conn)
        with open(os.path.join(f, "outgoing", "MNQ 12-26 Globex_MFFUEVAL1_Position.txt"), "w") as fh:
            fh.write("FLAT;0;0")
    if bar_t:
        for m in (1, 5):
            t0 = int(bar_t) - m * 60
            rows = [f"{t0 - i * m * 60},25000.25,25001,24999.5,25000.75,120" for i in range(5, -1, -1)]
            with open(os.path.join(f, "le_feed", f"MNQ_{m}m.csv"), "w") as fh:
                fh.write("\n".join(rows) + "\n")
    if open_t:
        p = os.path.join(f, "le_feed", "MNQ_1m_open.csv")
        with open(p, "w") as fh:
            fh.write(f"{int(open_t)},25000.25\n")
        os.utime(p, (open_t, open_t))
    return f


def hb(now, label="LIVE", trades=(), days=None, start="2026-10-13", kill=False, stage="levels", position=None):
    return {"t": int(now) - 60, "running": True, "adapter": "ninjatrader", "position": bool(position),
            "health": {"account": {"name": "MFFUEVAL1" if label == "LIVE" else "Sim101", "label": label, "enabled": True},
                       "kill": kill, "lit": {"stage": stage}},
            "acct": {"account": {"name": "MFFUEVAL1", "label": "LIVE ACCOUNT" if label == "LIVE" else label},
                     "eval": {"start": start, "days": dict(days or {})}, "trades": list(trades), "position": position,
                     "day_pnl": sum(float(t.get("pnl") or 0) for t in trades if t.get("day") == oc.trading_day(now))}}


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_ops_")
    old_env = {k: os.environ.get(k) for k in ("LE_OPS_PUSH",)}
    old_log_dir = oc.LOG_DIR
    oc.LOG_DIR = os.path.join(tmp, "ops_logs")                   # ops_log() writes here, not into logs/
    try:
        # ------------------------------------------------------------------ friendly errors
        samples = {
            "NinjaTrader folder not found: C:\\Users\\Owner\\Documents\\NinjaTrader 8\\incoming. Is NinjaTrader": "order folder",
            "FEED STALE: NinjaTrader bars missing or stale (1m 12 min old)": "bars are not reaching",
            "NinjaTrader reports DISCONNECTED": "lost its connection",
            "REFUSED: kill switch is engaged": "kill switch",
            f"LIVE account MFFUEVAL1 refused: confirm phrase missing (type exactly '{LIVE_PHRASE}')": "safety lock",
            "[supervisor] port 8766 is already in use by another process": "Another copy",
            "ModuleNotFoundError: No module named 'fastapi'": "package is missing",
            "error: Your local changes to the following files would be overwritten by merge": "changed by hand",
            "requests.exceptions.ConnectionError: Max retries exceeded (getaddrinfo failed)": "No internet",
            "ssl.SSLCertVerificationError: certificate verify failed": "clock is wrong",
            "OSError: [Errno 28] No space left on device": "disk is full",
            "PermissionError: [WinError 32] The process cannot access the file because it is being used by another process": "blocked a file",
            "UnicodeEncodeError: 'charmap' codec can't encode": "encoding",
            "live_state.json unreadable (Expecting value) - starting clean": "damaged",
            "[heartbeat] push failed: remote: Permission to x/y.git denied": "heartbeat",
            "MemoryError": "memory",
            "sqlite3.OperationalError: database is locked": "busy",
            "Traceback (most recent call last):": "unexpected error",
        }
        bad = []
        for text, want in samples.items():
            tr = oc.translate(text)
            if not tr or want.lower() not in tr["what"].lower() or not tr["fix"]:
                bad.append((text[:40], tr and tr["what"]))
        check(f"errors: {len(samples)} common log errors -> plain words + one fix", not bad, bad)
        check("errors: every table row has a key, a pattern, words and a fix", len(oc.ERRORS) >= 15 and all(len(r) == 4 and all(r) for r in oc.ERRORS)
              and set(oc.FIX) == {r[0] for r in oc.ERRORS})
        tr = oc.translate(f"refused: confirm phrase missing (type exactly '{LIVE_PHRASE}') at C:\\Users\\Owner\\x.py")
        check("errors: the excerpt never carries the live phrase or a path", LIVE_PHRASE not in tr["text"] and "Users" not in tr["text"], tr["text"])
        check("errors: unknown text -> None", oc.translate("all fine, 3 setups seen") is None and oc.translate("") is None)
        logs = os.path.join(tmp, "logs")
        os.makedirs(logs)
        now = ts(2026, 10, 20, 9, 40)
        with open(os.path.join(logs, f"server-{oc._et(now):%Y%m%d}.log"), "w", encoding="utf-8") as fh:
            fh.write("09:00:01 ok\n09:01:00 FEED STALE: NinjaTrader bars missing\n09:06:00 FEED STALE: NinjaTrader bars missing\n"
                     "09:07:00 ModuleNotFoundError: No module named 'x'\n")
        rows = oc.scan_logs(logs, now=now)
        check("logs: today's server log -> 2 kinds, FEED STALE counted twice", len(rows) == 2 and rows[0]["count"] == 2 and "bars" in rows[0]["what"], rows)
        lc = oc.check_logs(rows)
        check("logs: shown as yellow lines with the fix", len(lc) == 2 and all(c["level"] == oc.WARN and c["fix"] for c in lc))

        # ------------------------------------------------------------------ NinjaTrader folder, connection, feed
        now = ts(2026, 10, 20, 1, 45)                                 # Tuesday 01:45 ET, market open
        f = nt_tree(os.path.join(tmp, "a"), "CONNECTED", bar_t=now - 30, open_t=now - 20)
        check("NinjaTrader folder: incoming + outgoing -> OK", oc.check_nt_folder(f)["level"] == oc.OK)
        f2 = os.path.join(tmp, "b", "NinjaTrader 8")
        os.makedirs(os.path.join(f2, "outgoing"))
        c = oc.check_nt_folder(f2)
        check("NinjaTrader folder: incoming missing -> FIX: turn on the AT Interface", c["level"] == oc.BAD and "AT Interface" in c["fix"], c)
        check("NinjaTrader folder: none -> FIX", oc.check_nt_folder(os.path.join(tmp, "none"))["level"] == oc.BAD)
        conns = oc.nt_connections(f)
        check("connection files read, position files ignored", conns == {"MFFU Rithmic": "CONNECTED"}, conns)
        check("connection: CONNECTED -> OK", oc.check_nt_connection(conns, now)["level"] == oc.OK)
        c = oc.check_nt_connection({"MFFU Rithmic": "DISCONNECTED"}, now)
        check("connection: DISCONNECTED -> FIX: Connections menu", c["level"] == oc.BAD and "Connections" in c["fix"], c)
        check("connection: no file while the market is open -> WARN", oc.check_nt_connection({}, now)["level"] == oc.WARN)
        check("feed 1m + 5m fresh -> OK", oc.check_feed(f, 1, now)["level"] == oc.OK and oc.check_feed(f, 5, now)["level"] == oc.OK,
              (oc.check_feed(f, 1, now), oc.check_feed(f, 5, now)))
        late = now + 20 * 60
        c1 = oc.check_feed(f, 1, late)
        check("feed 1m 20 min old -> FIX: FEED STALE + keep the LE_BarFeed chart open", c1["level"] == oc.BAD and "STALE" in c1["text"]
              and "LE_BarFeed" in c1["fix"], c1)
        check("feed 5m 20 min old -> FIX", oc.check_feed(f, 5, late)["level"] == oc.BAD)
        sat = ts(2026, 10, 24, 12, 0)
        check("feed on Saturday: market closed -> INFO, not red", oc.check_feed(f, 1, sat)["level"] == oc.INFO)
        check("feed file missing -> FIX: add LE_BarFeed", oc.check_feed(f2, 1, now)["level"] == oc.BAD)
        check("1m open file fresh -> OK; missing -> WARN; old -> WARN",
              oc.check_open_file(f, now)["level"] == oc.OK and oc.check_open_file(f2, now)["level"] == oc.WARN
              and oc.check_open_file(f, late)["level"] == oc.WARN)
        check("last_bar_t reads the open time of the last row", oc.last_bar_t(os.path.join(f, "le_feed", "MNQ_1m.csv")) == int(now - 30) - 60)

        # ------------------------------------------------------------------ PC settings (fakes: no Windows here)
        U = lambda free: (lambda p: SimpleNamespace(free=free * 1e9))
        check("disk: 120 GB OK, 6 GB WARN, 1 GB FIX", oc.check_disk(usage=U(120))["level"] == oc.OK and oc.check_disk(usage=U(6))["level"] == oc.WARN
              and oc.check_disk(usage=U(1))["level"] == oc.BAD)
        probe = lambda off: (lambda url: {"ok": True, "date": 1000.0 + off, "t0": 999.8, "t1": 1000.2})
        net = oc.internet(probe=probe(0.4))
        check("internet: answers -> up, clock drift from the Date header", net["up"] and abs(net["drift_s"] - 0.4) < 1e-6, net)
        check("clock: 0.4 s OK, 5 s WARN, 90 s FIX with 'Sync now'", oc.check_clock(net)["level"] == oc.OK
              and oc.check_clock(oc.internet(probe=probe(5)))["level"] == oc.WARN
              and oc.check_clock(oc.internet(probe=probe(-90)))["level"] == oc.BAD and "Sync now" in oc.check_clock(oc.internet(probe=probe(-90)))["fix"])
        # the entry guard counts only the drift the probe proves (owner's busy Surface 2026-10-25 read "5.0 s ahead")
        from engine import guards as _G
        _real = oc.internet
        try:
            slow = lambda off, rtt: (lambda **k: _real(probe=lambda u: {"ok": True, "date": 1000.0 + off, "t0": 1000.0 - rtt / 2, "t1": 1000.0 + rtt / 2}))
            oc.internet = slow(-5.0, 10.0)
            g1 = _G.clock_probe()
            oc.internet = slow(-8.0, 0.2)
            g2 = _G.clock_probe()
            oc.internet = slow(7.0, 0.2)
            g3 = _G.clock_probe()
            oc.internet = slow(0.0, 0.2)
            g4 = _G.clock_probe()
        finally:
            oc.internet = _real
        check("clock guard: '5 s ahead' on a 10 s round trip proves nothing (0)", g1 == 0.0, g1)
        check("clock guard: 8 s ahead on a fast round trip still proves > 5 s", g2 is not None and g2 < -5.0, g2)
        check("clock guard: 7 s behind on a fast round trip still blocks", g3 is not None and g3 > 5.0, g3)
        check("clock guard: right clock = 0", g4 == 0.0, g4)
        down = oc.internet(probe=lambda u: {"ok": False, "t0": 0, "t1": 0})
        check("internet down -> FIX; clock not checked", not down["up"] and oc.check_internet(down)["level"] == oc.BAD
              and oc.check_clock(down)["level"] == oc.SKIP)

        def pc_run(standby, hib, lid):
            def run(args):
                v = {"STANDBYIDLE": standby, "HIBERNATEIDLE": hib, "LIDACTION": lid}[args[-1]]
                return 0, (f"Power Setting GUID: x\n  Minimum Possible Setting: 0x00000000\n  Maximum Possible Setting: 0xffffffff\n"
                           f"Current AC Power Setting Index: 0x{v:08x}\nCurrent DC Power Setting Index: 0x00000384\n")
            return run
        check("power: never sleeps, lid does nothing -> OK", oc.check_power(run=pc_run(0, 0, 0), is_windows=True)["level"] == oc.OK)
        c = oc.check_power(run=pc_run(1800, 0, 1), is_windows=True)
        check("power: sleeps after 30 min + lid -> WARN with the Power fix", c["level"] == oc.WARN and "30 min" in c["text"] and "lid" in c["text"]
              and "Never" in c["fix"], c)
        check("power: not Windows -> SKIP", oc.check_power(is_windows=False)["level"] == oc.SKIP)
        reg = lambda vals: (lambda hive, key, value: vals.get(value))
        nokey = lambda hive, key: False
        later = dt.datetime.fromtimestamp(now + 20 * 86400, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        check("Windows Update: paused 20 days -> OK", oc.check_windows_update(now, reg=reg({"PauseUpdatesExpiryTime": later}), key_exists=nokey,
                                                                            is_windows=True)["level"] == oc.OK)
        check("Windows Update: not paused -> WARN 'Pause updates'", "Pause" in oc.check_windows_update(now, reg=reg({}), key_exists=nokey,
                                                                                                       is_windows=True)["fix"])
        c = oc.check_windows_update(now, reg=reg({}), key_exists=lambda h, k: True, is_windows=True)
        check("Windows Update: restart pending -> WARN restart after 16:00 ET", c["level"] == oc.WARN and "16:00" in c["fix"], c)
        check("OneDrive: NinjaTrader folder in OneDrive -> WARN; else OK",
              oc.check_onedrive(r"C:\Users\O\OneDrive\Documents\NinjaTrader 8")["level"] == oc.WARN and oc.check_onedrive(f)["level"] == oc.OK)
        c = oc.check_cfa(f, reg=reg({"EnableControlledFolderAccess": 1}), is_windows=True)
        check("Controlled Folder Access on but Python can write -> OK, fix names python", c["level"] == oc.OK and "on" in c["text"], c)
        check("Controlled Folder Access off -> OK", oc.check_cfa(f, reg=reg({"EnableControlledFolderAccess": 0}), is_windows=True)["level"] == oc.OK)
        check("decimal ',' -> WARN; '.' -> OK", oc.check_decimal(reg=reg({"sDecimal": ","}), is_windows=True)["level"] == oc.WARN
              and oc.check_decimal(reg=reg({"sDecimal": "."}), is_windows=True)["level"] == oc.OK)
        vs = oc.check_versions(run=lambda a: (0, "git version 2.46.0.windows.1"))
        check("python / git / packages -> OK here", [c["level"] for c in vs] == [oc.OK, oc.OK, oc.OK], vs)
        check("git missing -> FIX install Git", oc.check_versions(run=lambda a: (1, ""))[1]["level"] == oc.BAD)
        au = oc.check_auto()
        check("auto-update + auto-resume lines present", {c["key"] for c in au} >= {"autoupdate", "autoresume"}, au)

        # ------------------------------------------------------------------ server, heartbeat, account
        check("server down -> FIX: START DASHBOARD", oc.check_server(None)[0]["level"] == oc.BAD and "START DASHBOARD" in oc.check_server(None)[0]["fix"])
        s = oc.check_server({"ok": True, "uptime_s": 600, "bot_running": False})
        check("server up, bot stopped -> FIX: press Start", s[0]["level"] == oc.OK and s[1]["level"] == oc.BAD and "Start" in s[1]["fix"], s)
        ping = {"ok": True, "uptime_s": 600, "bot_running": True, "heartbeat": {"enabled": True, "last": {"at": now - 120, "ok": True}}}
        check("heartbeat pushed 2 min ago -> OK", oc.check_heartbeat(ping, {}, now)["level"] == oc.OK)
        c = oc.check_heartbeat({**ping, "heartbeat": {"enabled": True, "last": {"at": now - 120, "ok": False, "error": "Authentication failed"}}}, {}, now)
        check("heartbeat push failed -> FIX: git sign-in", c["level"] == oc.BAD and "sign in" in c["fix"], c)
        check("heartbeat off -> WARN", oc.check_heartbeat({**ping, "heartbeat": {"enabled": False}}, {}, now)["level"] == oc.WARN)
        check("account LIVE -> OK", oc.check_account(hb(now), now)[0]["level"] == oc.OK)
        c = oc.check_account(hb(now, "SIM"), now)
        check("account Sim -> WARN 'not your eval'", c[0]["level"] == oc.WARN and "not your eval" in c[0]["text"], c)
        c = oc.check_account(hb(now, kill=True), now)
        check("kill switch on -> FIX", any(x["key"] == "kill" and x["level"] == oc.BAD for x in c), c)
        dis = hb(now)
        dis["health"]["account"].update(enabled=False, disabled=f"LIVE account MFFUEVAL1 refused: confirm phrase missing (type exactly '{LIVE_PHRASE}')")
        c = oc.check_account(dis, now)[0]
        check("account disabled -> FIX, the live phrase never shown", c["level"] == oc.BAD and LIVE_PHRASE not in json.dumps(c), c)

        # ------------------------------------------------------------------ notices
        green = [oc._c("server", "Bot server", oc.OK, "up"), oc._c("bot", "Bot", oc.OK, "running"), oc._c("account", "Account", oc.OK, "x"),
                 oc._c("nt_conn", "NinjaTrader connection", oc.OK, "x"), oc._c("feed_1m", "Bar feed 1m", oc.OK, "x"),
                 oc._c("power", "Power / sleep", oc.WARN, "sleeps", "fix it")]       # a yellow non-session line never blocks "all green"
        v = oc.account_view(hb(now, days={"2026-10-14": 700.0}), now)
        p = oc.presession_notice(green, v, now)
        check("pre-session: 'All green for tonight' + eval line", p["title"] == "All green for tonight" and "to go" in p["body"]
              and p["kind"] == "ops" and p["key"] == "ops:pre:2026-10-20", p)
        red = green[:4] + [oc._c("feed_1m", "Bar feed 1m", oc.BAD, "last bar 14 min old (FEED STALE: no new entries)", oc.FIX["feed"]),
                           oc._c("bot", "Bot", oc.BAD, "server up, bot STOPPED", "Dashboard > Start (on your eval account).")]
        p = oc.presession_notice(red, v, now)
        check("pre-session: the exact fix (feed stale) + how many more", p["title"].startswith("Fix before 02:00 ET") and "LE_BarFeed" in p["body"]
              and "+1 more" in p["body"], p)
        p = oc.presession_notice(green[:2] + [oc._c("account", "Account", oc.WARN, "orders go to Sim101 (Sim), not your eval", "Stop, choose the eval")], v, now)
        check("pre-session: on Sim instead of the eval -> says so", "Account" in p["title"] and "Sim101" in p["body"], p)
        eod = ts(2026, 10, 20, 16, 6)
        tr_today = [{"day": "2026-10-20", "entry_t": int(ts(2026, 10, 20, 3, 10)), "pnl": 1812.0},
                    {"day": "2026-10-16", "entry_t": int(ts(2026, 10, 16, 9, 10)), "pnl": -366.0}]
        v = oc.account_view(hb(eod, trades=tr_today, days={"2026-10-16": -366.0, "2026-10-20": 1812.0}), eod)
        p = oc.eod_notice(v, eod)
        check("day summary: trades, P&L, $ to go, session X of 10", "1 trade (1 won), +$1,812" in p["body"] and "$1,554 to go" in p["body"]
              and "session 6 of 10" in p["body"], p["body"])
        p = oc.eod_notice(oc.account_view(hb(eod, days={}), eod), eod)
        check("day summary: no trade today", p["body"].startswith("No trade today"), p["body"])
        sun = ts(2026, 10, 25, 18, 0)
        wk = [{"day": d, "entry_t": int(ts(2026, 10, int(d[-2:]), 4)), "pnl": x} for d, x in
              (("2026-10-19", 900.0), ("2026-10-21", -400.0), ("2026-10-23", 1500.0), ("2026-10-16", 50.0))]
        v = oc.account_view({**hb(sun, trades=wk, days={"2026-10-19": 900.0}), "t": int(sun) - 60}, sun)
        p = oc.weekly_notice(v, {"last_backup_t": sun - 3600}, green, sun)
        check("week report: Mon-Fri trades only, W/L, P&L, pace, eval, PC health", "3 trades (2 won, 1 lost), +$2,000" in p["body"]
              and "on pace" in p["body"] and "Eval:" in p["body"] and p["key"] == "ops:week:2026-W43" and "Oct 19-Oct 23" in p["title"], p)
        idle_now = ts(2026, 10, 21, 16, 6)
        v = oc.account_view(hb(idle_now, trades=[{"day": "2026-10-16", "entry_t": int(ts(2026, 10, 16, 9)), "pnl": 100.0}],
                               days={"2026-10-16": 100.0}), idle_now)
        p = oc.inactivity_notice(v, idle_now)
        check("MFFU inactivity: day 5 without a trade -> 'place 1 MNQ by hand or let the min-days trade run'", p is not None and "5 days" in p["title"]
              and "1 MNQ by hand" in p["body"] and "min-days" in p["body"], p)
        v4 = oc.account_view(hb(idle_now, trades=[{"day": "2026-10-17", "entry_t": int(ts(2026, 10, 17, 9)), "pnl": 1.0}]), idle_now)
        check("MFFU inactivity: day 4 -> nothing; Sim account -> nothing", oc.inactivity_notice(v4, idle_now) is None
              and oc.inactivity_notice(oc.account_view(hb(idle_now, "SIM", trades=[{"day": "2026-10-16", "pnl": 1}]), idle_now), idle_now) is None)
        vp = oc.account_view(hb(eod, days={"2026-10-14": 1200.0, "2026-10-20": 1900.0}), eod)
        p = oc.eval_result_notice(vp, eod)
        check("eval passed -> push with funded next steps", p is not None and "PASSED" in p["title"] and "funded" in p["body"]
              and p["key"] == "ops:eval:passed:2026-10-13", p)
        vf = oc.account_view(hb(eod, days={"2026-10-14": -1200.0, "2026-10-20": -900.0}), eod)
        p = oc.eval_result_notice(vf, eod)
        check("eval failed -> push: buy a new one with the discount, stagger rule", p is not None and "failed" in p["title"].lower()
              and oc.OWNER_PRICE in p["body"] and "discount" in p["body"] and "Stagger" in p["body"], p)
        check("eval open -> no pass / fail push", oc.eval_result_notice(oc.account_view(hb(eod, days={"2026-10-14": 500.0}), eod), eod) is None)
        r = oc.next_roll(dt.date(2026, 11, 20))
        check("roll: next is Thu 2026-12-10, MNQ 12-26 -> MNQ 03-27", r == (dt.date(2026, 12, 10), "MNQ 12-26", "MNQ 03-27"), r)
        p = oc.roll_notice(ts(2026, 12, 3, 16, 6))
        check("roll: a week before -> chart to MNQ 03-27, 30 days, steps", p is not None and "MNQ 03-27" in p["body"] and "30" in p["body"]
              and "Wed Dec 09" in p["body"] and p["key"].endswith(":week"), p)
        p1 = oc.roll_notice(ts(2026, 12, 9, 1, 45))
        check("roll: the day before -> a second reminder", p1 is not None and "tomorrow" in p1["title"] and p1["key"].endswith(":tomorrow"), p1)
        check("roll: 2 weeks before / on the day -> nothing", oc.roll_notice(ts(2026, 11, 25, 16, 6)) is None and oc.roll_notice(ts(2026, 12, 10, 16, 6)) is None)
        blob = json.dumps([oc.presession_notice(red, v, now), oc.eod_notice(v, eod)])
        check("notices: no paths, never the live phrase", "Users" not in blob and LIVE_PHRASE not in blob)

        # ------------------------------------------------------------------ watch: drops + recovery, once each
        st = {"sent": {}}
        ctx = {"folder": f, "net": {"up": False}, "hb": {}}
        t1 = ts(2026, 10, 20, 2, 14)
        check("internet down: nothing can be sent yet", oc.watch(ctx, st, t1) == [] and st.get("net_down_since") == int(t1))
        check("still down 5 min later: nothing", oc.watch(ctx, st, t1 + 300) == [])
        ctx["net"] = {"up": True}
        n = oc.watch(ctx, st, t1 + 17 * 60)
        check("internet back -> one notice 'down 17 min, 02:14-02:31'", len(n) == 1 and "17 min" in n[0]["title"] and "02:14" in n[0]["body"]
              and "net_down_since" not in st, n)
        with open(os.path.join(f, "outgoing", "MFFU Rithmic.txt"), "w") as fh:
            fh.write("DISCONNECTED")
        a = oc.watch(ctx, st, t1 + 20 * 60)
        b = oc.watch(ctx, st, t1 + 25 * 60)
        c = oc.watch(ctx, st, t1 + 30 * 60)
        check("NinjaTrader disconnected: one notice after 2 checks in a row, not again", a == [] and len(b) == 1 and "disconnected" in b[0]["title"]
              and c == [], (a, b, c))
        with open(os.path.join(f, "outgoing", "MFFU Rithmic.txt"), "w") as fh:
            fh.write("CONNECTED")
        d = oc.watch(ctx, st, t1 + 40 * 60)
        check("NinjaTrader reconnected -> one recovery notice 'after 20 min'", len(d) == 1 and "reconnected" in d[0]["title"] and "20 min" in d[0]["body"]
              and "nt_alerted" not in st and oc.watch(ctx, st, t1 + 45 * 60) == [], d)

        # ------------------------------------------------------------------ tick: what is due, sent once
        os.environ.pop("LE_OPS_PUSH", None)
        sent = []
        sender = lambda p: (sent.append(p), {"sent": 1})[1]
        spath = os.path.join(tmp, "ops_state.json")
        pre = ts(2026, 10, 20, 1, 42)
        H = hb(pre, days={"2026-10-14": 700.0}, trades=[{"day": "2026-10-19", "entry_t": int(ts(2026, 10, 19, 3)), "pnl": 700.0}])
        ctx = {"now": pre, "folder": f, "ping": ping, "hb": H, "net": {"up": True, "n": 3, "drift_s": 0.2}, "state": {}, "light": True}
        res = oc.tick(now=pre, ctx=ctx, state=oc.load_state(spath), sender=sender, state_path=spath, do_backup=False)
        check("tick 01:42 ET: the pre-session notice goes out", [p["key"] for p in sent] == ["ops:pre:2026-10-20"], [p["key"] for p in sent])
        oc.tick(now=pre + 300, ctx={**ctx, "now": pre + 300}, state=oc.load_state(spath), sender=sender, state_path=spath, do_backup=False)
        check("tick 5 min later: not sent twice (data/ops_state.json keys)", len(sent) == 1, [p["key"] for p in sent])
        mid = ts(2026, 10, 20, 11, 0)
        oc.tick(now=mid, ctx={**ctx, "now": mid}, state=oc.load_state(spath), sender=sender, state_path=spath, do_backup=False)
        check("tick 11:00 ET: nothing due", len(sent) == 1)
        e1 = ts(2026, 10, 20, 16, 7)
        oc.tick(now=e1, ctx={**ctx, "now": e1, "hb": {**H, "t": int(e1) - 60}}, state=oc.load_state(spath), sender=sender, state_path=spath, do_backup=False)
        check("tick 16:07 ET: the day summary", [p["key"] for p in sent][-1] == "ops:eod:2026-10-20", [p["key"] for p in sent])
        failing = lambda p: {"sent": 0, "errors": ["URLError"]}
        st2 = {"sent": {}}
        oc.send(oc.eod_notice(oc.account_view(H, e1), e1), st2, sender=failing)
        check("a push that failed on the network is tried again next run", st2["sent"] == {})
        os.environ["LE_OPS_PUSH"] = "0"
        r = oc.send(oc.eod_notice(oc.account_view(H, e1), e1), {"sent": {}}, sender=sender)
        check("LE_OPS_PUSH=0: recorded, not pushed", r.get("skipped") and len([p for p in sent if p["key"] == "ops:eod:2026-10-20"]) == 1)
        os.environ.pop("LE_OPS_PUSH", None)
        D = oc.due(ts(2026, 10, 25, 18, 0))
        check("due: Sunday 18:00 ET = weekly; weekday 01:45 = pre-session; 16:10 = day summary",
              D["weekly"] and not D["eod"] and oc.due(ts(2026, 10, 20, 1, 45))["presession"] and oc.due(ts(2026, 10, 20, 16, 10))["eod"])

        # ------------------------------------------------------------------ backup + log rotation
        r0 = os.path.join(tmp, "root")
        os.makedirs(os.path.join(r0, "data", "nt_bars"))
        for name, body in (("live_state.json", "{}"), ("ninjatrader_state.json", "{}"), ("shadow_ledger.json", "{}"), ("lit_journal.jsonl", ""),
                           ("push.json", '{"vapid_private": "SECRET"}'), ("push_pc_key.json", "SECRET"), ("tv.json", "SECRET"),
                           ("nt_bars/NQ_1m.csv", "1,2,3")):
            with open(os.path.join(r0, "data", name), "w") as fh:
                fh.write(body)
        dest = os.path.join(r0, "backups")
        os.makedirs(dest)
        old = os.path.join(dest, "le-backup-20261001-1640.zip")
        with zipfile.ZipFile(old, "w") as z:
            z.writestr("x", "y")
        os.utime(old, (time.time() - 20 * 86400, time.time() - 20 * 86400))
        b = oc.backup(root=r0, dest=dest)
        names = zipfile.ZipFile(os.path.join(dest, b["file"])).namelist() if b.get("ok") else []
        check("backup: state, ledgers, NinjaTrader state, nt_bars in one zip", b.get("ok") and {"data/live_state.json", "data/ninjatrader_state.json",
              "data/shadow_ledger.json", "data/nt_bars/NQ_1m.csv"} <= set(n.replace("\\", "/") for n in names), (b, names))
        check("backup: no secrets (push keys, TradingView login)", not any(("push" in n or "tv.json" in n) for n in names), names)
        check("backup: zips older than 14 days deleted", b.get("deleted") == 1 and not os.path.exists(old))
        L = os.path.join(r0, "logs")
        os.makedirs(L)
        day_old = time.time() - 3 * 86400
        for name, age in (("server-20261017.log", day_old), ("server-today.log", time.time()), ("ninjatrader_oif.log", day_old)):
            with open(os.path.join(L, name), "w") as fh:
                fh.write("line\n" * 10)
            os.utime(os.path.join(L, name), (age, age))
        with open(os.path.join(L, "server-20260801.log.gz"), "wb") as fh:
            fh.write(gzip.compress(b"x"))
        os.utime(os.path.join(L, "server-20260801.log.gz"), (time.time() - 60 * 86400,) * 2)
        rr = oc.rotate_logs(L)
        check("logs: yesterday's log gzipped, today's kept, 60-day-old .gz deleted, order audit kept",
              rr["gzipped"] == 1 and os.path.exists(os.path.join(L, "server-20261017.log.gz")) and os.path.exists(os.path.join(L, "server-today.log"))
              and not os.path.exists(os.path.join(L, "server-20260801.log.gz")) and os.path.exists(os.path.join(L, "ninjatrader_oif.log")), rr)
        check("backup due: once a day after 16:35 ET, not during trading time",
              oc.backup_due({}, ts(2026, 10, 20, 16, 40)) and not oc.backup_due({"last_backup_t": ts(2026, 10, 20, 16, 40)}, ts(2026, 10, 20, 17, 0))
              and not oc.backup_due({"last_backup_t": ts(2026, 10, 18, 16, 40)}, ts(2026, 10, 20, 10, 0))
              and oc.backup_due({"last_backup_t": ts(2026, 10, 18, 16, 40)}, ts(2026, 10, 20, 0, 30)))

        # ------------------------------------------------------------------ update guard, heartbeat file, push helper
        from engine import autoupdate
        orig_flat, orig_hb = autoupdate.files_flat_reason, oc.hb_last
        try:
            autoupdate.files_flat_reason = lambda now=None, root=None: "a routed position is open"
            check("update guard: a trade open -> 1 (never update)", oc.update_guard(ts(2026, 10, 20, 20, 0))[0] == 1)
            autoupdate.files_flat_reason = lambda now=None, root=None: None
            oc.hb_last = lambda path=None: {}
            check("update guard: trading time -> 2 (ask first); evening flat -> 0",
                  oc.update_guard(ts(2026, 10, 20, 9, 0))[0] == 2 and oc.update_guard(ts(2026, 10, 20, 17, 30))[0] == 0)
            t9 = ts(2026, 10, 20, 17, 30)
            oc.hb_last = lambda path=None: {"t": int(t9) - 30, "health": {"lit": {"stage": "limit"}}}
            check("update guard: a LIT limit armed (per the heartbeat) -> 1", oc.update_guard(t9)[0] == 1)
        finally:
            autoupdate.files_flat_reason, oc.hb_last = orig_flat, orig_hb
        lp = os.path.join(tmp, "hb_last.json")
        bot = SimpleNamespace(cfg={"adapter": "paper"}, adapter=None, health={}, state={}, ledger=[], running=True, started_at=None)
        hbo = heartbeat.Heartbeat(bot, last_path=lp)
        pl = hbo.payload()
        check("heartbeat payload carries the small 'ops' block", isinstance(pl.get("ops"), dict) and len(json.dumps(pl["ops"])) < 600, pl.get("ops"))
        heartbeat.save_last(pl, {"ok": True, "commit": "abc"}, lp)
        got = oc.hb_last(lp)
        check("heartbeat_last.json written + read back (payload, push result)", got.get("running") is True and got["_push"]["ok"] is True, got.get("_push"))
        out = []
        r = push.pc_send_now(push.text_payload("PC", "ops", "t", "b", key="k"), sync={"private": None, "subs": []})
        check("push.pc_send_now: not linked -> skipped, never raises", r.get("skipped") == "not configured", r)
        priv, _pub = push.generate_keys()
        sub = {"endpoint": "https://web.push.apple.com/x", "keys": {"p256dh": "a", "auth": "b"}}
        r = push.pc_send_now(push.text_payload("PC", "ops", "t", "b", key="k"), sync={"private": priv, "subs": [sub]},
                             sender=lambda s, d, pr, pu: (out.append(d), 201)[1])
        check("push.pc_send_now: linked -> sent through the sender", r.get("sent") == 1 and b'"kind":"ops"' in out[0], r)
        src = open(os.path.join(ROOT, "engine", "push.py"), encoding="utf-8").read()
        check("push.pc_notify always pushes kind 'ops'", re.search(r'kind"\) in \("fill", "outcome", "test", "pc", "ops"\)', src) is not None)
        from tools import cloud_monitor as cm
        cell = cm._ops_cell({"checks_t": int(now), "bad": 1, "warn": 2, "first_fix": "Bar feed 1m: open NinjaTrader", "backup_t": int(now) - 3600,
                             "disk_free_gb": 88.2})
        check("cloud README row 'PC checks': red / yellow, first fix, backup, disk", "1 red, 2 yellow" in cell and "fix: Bar feed" in cell
              and "backup" in cell and "88 GB" in cell, cell)

        # ------------------------------------------------------------------ the double-click files (static checks)
        def read(rel):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                return fh.read()
        bats = ["UPDATE.bat", "START_DASHBOARD.bat", "HEALTH_CHECK.bat", "STOP_BOT.bat", "SETUP_SHORTCUTS.bat"]
        ps1 = ["scripts/make_shortcuts.ps1", "scripts/install_ops_task.ps1"]
        missing = [b for b in bats + ps1 + ["scripts/ops_tick.py", "docs/DAILY_CHECKLIST.md", "docs/TROUBLESHOOTING.md"]
                   if not os.path.exists(os.path.join(ROOT, b))]
        check("all helper files exist", not missing, missing)
        probs = []
        for b in bats:
            s = read(b)
            labels = {m.lower() for m in re.findall(r"^:(\w+)", s, re.M)}
            gotos = {m.lower() for m in re.findall(r"goto :?(\w+)", s, re.I)} - {"eof"}
            if gotos - labels:
                probs.append(f"{b}: goto without label {gotos - labels}")
            if not s.lstrip().lower().startswith("@echo off"):
                probs.append(f"{b}: no @echo off")
            if 'cd /d "%~dp0"' not in s:
                probs.append(f"{b}: does not cd to its folder")
            for ln in s.splitlines():
                t = ln.strip()
                if t.lower().startswith("rem") or t.startswith("::"):
                    continue
                if t.count("(") != t.count(")"):
                    probs.append(f"{b}: unbalanced () in: {t[:60]}")
                if t.count('"') % 2:
                    probs.append(f"{b}: odd quotes in: {t[:60]}")
            for bad in ("api/live/start", "golive", "--enable-auto-resume", "NINJATRADER_LIVE=1", "armed", "/api/live/arm"):
                if bad.lower() in s.lower():
                    probs.append(f"{b}: contains {bad}")
        check("bat files: every goto has its label, @echo off, cd to the folder, balanced quotes / ()", not probs, probs)
        u = read("UPDATE.bat")
        order = [u.find(x) for x in ("--update-guard", "stop_bot.ps1\" -KeepAutostart", "-m engine.autoupdate --pull",
                                      "pip install -r requirements.txt", "scripts\\run_bot.ps1", "--wait-server", "--after-update")]
        check("UPDATE.bat: guard -> stop (keeps auto-resume) -> pull main (the auto-update's fast-forward) -> pip -> run_bot in "
              "its own window -> self-test, in order",
              all(i >= 0 for i in order) and order == sorted(order) and 'start "Liquidity Engine bot"' in u, order)
        check("UPDATE.bat: a failed pull still restarts the bot (no goto out between pull and restart)",
              "goto" not in u[u.find("-m engine.autoupdate --pull"):u.find("scripts\\run_bot.ps1")])
        check("UPDATE.bat: trade open -> refuses; trading time -> asks Y", "GUARD%\"==\"1\" goto :intrade" in u and "set /p" in u)
        sd = read("START_DASHBOARD.bat")
        check("START_DASHBOARD.bat: pings, starts run_bot only when down, opens localhost:8766",
              "/api/health/ping" in sd and "run_bot.ps1" in sd and 'start "" "%URL%"' in sd and "8766" in sd)
        check("HEALTH_CHECK.bat runs python -m engine.ops_checks", "-m engine.ops_checks" in read("HEALTH_CHECK.bat"))
        sb = read("STOP_BOT.bat")
        check("STOP_BOT.bat asks first, then the full stop (clears auto-resume)", "set /p" in sb and "stop_bot.ps1\"\n" in sb.replace("\r", ""))
        pprobs = []
        for p in ps1:
            s = read(p)
            body = re.sub(r"<#.*?#>", "", s, flags=re.S)
            body = re.sub(r"'[^'\n]*'", "''", body)
            body = re.sub(r'"(?:[^"`\n]|`.)*"', '""', body)
            for o, c_ in ("{}", "()", "[]"):
                if body.count(o) != body.count(c_):
                    pprobs.append(f"{p}: {o}{c_} {body.count(o)}/{body.count(c_)}")
            if "param(" not in s or "$ErrorActionPreference" not in s:
                pprobs.append(f"{p}: no param / ErrorActionPreference")
            if "-DryRun" not in s and "$DryRun" not in s:
                pprobs.append(f"{p}: no -DryRun")
        check("ps1: balanced braces / parens / brackets, param block, -DryRun", not pprobs, pprobs)
        sc = read("scripts/make_shortcuts.ps1")
        check("shortcuts: LE START (START_DASHBOARD.bat = the Start page) and LE STOP BOT on the desktop, the older icons removed",
              all(x in sc for x in ("'LE START'", "START_DASHBOARD.bat", "'LE STOP BOT'", "STOP_BOT.bat", "$retired"))
              and all(x in sc for x in ("'LE UPDATE'", "'LE DASHBOARD'", "'LE HEALTH CHECK'", "'LE START BOT'"))
              and "GetFolderPath('Desktop')" in sc and "File = 'UPDATE.bat'" not in sc)
        check("START_DASHBOARD.bat opens the Start page and waits up to 5 min for the server (logon)",
              "/?page=start" in sd and "lss 150" in sd)
        it = read("scripts/install_ops_task.ps1")
        check("ops task: pythonw scripts\\ops_tick.py every 5 min, limited user, not elevated", "pythonw.exe" in it and "ops_tick.py" in it
              and "New-TimeSpan -Minutes 5" in it and "RunLevel Limited" in it and "Highest" not in it)
        hits = [r for r in bats + ps1 + ["scripts/ops_tick.py", "engine/ops_checks.py", "tests/test_ops.py", "docs/DAILY_CHECKLIST.md",
                                         "docs/TROUBLESHOOTING.md"] if os.path.exists(os.path.join(ROOT, r)) and LIVE_PHRASE in read(r)]
        check("the live phrase is written in none of the new files", not hits, hits)
        gi = read(".gitignore")
        check(".gitignore: backups/ and data/ops_state.json", "backups/" in gi and "data/ops_state.json" in gi)
        ga = read(".gitattributes")
        check(".gitattributes: .bat files check out with CRLF", "*.bat text eol=crlf" in ga)
        links = read("README.md") + read("docs/GO_LIVE_TONIGHT.md")
        check("README + GO_LIVE link the daily checklist and troubleshooting", "docs/DAILY_CHECKLIST.md" in links and "TROUBLESHOOTING.md" in links)
    finally:
        oc.LOG_DIR = old_log_dir
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(RES)
    print(f"ops: {sum(RES)}/{n} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
