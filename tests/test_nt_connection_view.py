"""Is NinjaTrader connected? (engine/ninjatrader.connection_view, 2026-11-03)

2026-11-02 the heartbeat's nt_log.outgoing.connections showed only "Simulation=CONNECTED" while the MFFU connection fed
live prices: NinjaTrader's AT Interface writes outgoing\\<connection>.txt only when a connection changes state, so a
connection that was already up can have no file. The bot now also counts NinjaTrader's live accounts (le_feed\\accounts.csv,
a fresh non-Sim row) and live bars (a 1-minute bar closed in the last 4 minutes, or LE_Feed's status connected=1).

Checks: the view for each case, the MFFU entry refusal ("every connection DISCONNECTED") no longer fires on a stale
Simulation=DISCONNECTED file while the MFFU account is live, Sim101 keeps the old rule, the PC health check, the
heartbeat's outgoing summary and the botctl folder probe. Nothing here changes an entry, exit, stop, target or size.
Run: python -X utf8 -m tests.test_nt_connection_view
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import ninjatrader as nt  # noqa: E402
from engine import nt_log, ops_checks, botctl  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""), flush=True)
    if not ok:
        FAILS.append(name)


def folder(base, conns=None, accts=None, bar_t=None, status=None):
    if os.path.isdir(base):
        shutil.rmtree(base)
    for d in ("incoming", "outgoing", "le_feed"):
        os.makedirs(os.path.join(base, d))
    for k, v in (conns or {}).items():
        with open(os.path.join(base, "outgoing", k + ".txt"), "w") as fh:
            fh.write(v)
    if accts is not None:
        with open(os.path.join(base, "le_feed", "accounts.csv"), "w") as fh:
            fh.write("name,time,cash,realized,unrealized,netliq\n" + "".join(f"{n},{t},50000,0,0,50000\n" for n, t in accts))
    if bar_t is not None:
        with open(os.path.join(base, "le_feed", "MNQ_1m.csv"), "w") as fh:
            fh.write("time,open,high,low,close,volume\n" + f"{bar_t - 60},1,2,0,1,5\n{bar_t},1,2,0,1,5\n")
    if status is not None:
        with open(os.path.join(base, "le_feed", "le_feed_status.txt"), "w") as fh:
            fh.write(status + "\n")
    return base


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_connview_")
    now = int(time.time())
    try:
        f = os.path.join(tmp, "NinjaTrader 8")
        # 1. the 2026-11-02 case: only Simulation in outgoing, the MFFU account live in accounts.csv, bars flowing
        folder(f, {"Simulation": "CONNECTED"}, [("Sim101", now - 20), ("MFFUEVAL50K123", now - 20)], bar_t=now - 90)
        v = nt.connection_view(nt.NinjaTraderAdapter({"nt_folder": f, "nt_account": "Sim101",
                                                      "nt_state_path": os.path.join(tmp, "s.json")}, readonly=True).connections(), f, now)
        check("1. Simulation file only + live MFFU account + live bars -> connected, all three reasons",
              v["connected"] is True and v["via"] == ["connection file", "live account in accounts.csv", "live bars"], v)
        check("1b. ... with a plain note that the file alone is not the whole story", bool(v["note"]) and "Simulation=CONNECTED only" in v["note"], v)
        check("1c. live accounts counted, never named", v["live_accounts"] == 1 and "MFFU" not in str(v), v)
        # 2. no file at all, but a live account: connected (was "no connection file")
        folder(f, {}, [("MFFUEVAL50K123", now - 30)])
        check("2. no connection file + live account -> connected", nt.connection_view({}, f, now)["connected"] is True)
        # 3. no file, nothing fresh: unknown (as before)
        folder(f, {}, [("MFFUEVAL50K123", now - 3600)], bar_t=now - 3600)
        check("3. no file, stale accounts + stale bars -> None (unknown, as before)", nt.connection_view({}, f, now)["connected"] is None)
        # 4. every file DISCONNECTED and nothing fresh: disconnected (as before)
        folder(f, {"MFFU": "DISCONNECTED"}, [("MFFUEVAL50K123", now - 3600)])
        check("4. all DISCONNECTED, nothing fresh -> False (as before)",
              nt.connection_view({"MFFU": "DISCONNECTED"}, f, now)["connected"] is False)
        # 5. live bars alone (accounts.csv missing) and LE_Feed's status alone
        folder(f, {"Simulation": "DISCONNECTED"}, None, bar_t=now - 70)
        check("5a. stale DISCONNECTED file + a 1m bar closed 10 s ago -> connected",
              nt.connection_view({"Simulation": "DISCONNECTED"}, f, now)["connected"] is True)
        folder(f, {}, None, status=f"{now - 30},source=addon,instruments=MNQ 12-26,last_1m=,resubs=0,connected=1")
        check("5b. LE_Feed status connected=1 (fresh) -> connected", nt.connection_view({}, f, now)["connected"] is True)
        folder(f, {}, None, status=f"{now - 3000},source=addon,instruments=MNQ 12-26,last_1m=,resubs=0,connected=1")
        check("5c. ... but not when the status is 50 min old", nt.connection_view({}, f, now)["connected"] is None)
        # 6. the entry refusal: MFFU account live, only a stale Simulation=DISCONNECTED file -> NOT refused
        folder(f, {"Simulation": "DISCONNECTED"}, [("MFFUEVAL50K123", now - 20)])
        mk = lambda acct: nt.NinjaTraderAdapter({"nt_folder": f, "nt_account": acct, "nt_state_path": os.path.join(tmp, acct + ".json")},
                                                readonly=True, clock=lambda: now)
        ad = mk("MFFUEVAL50K123")
        check("6a. MFFU account live in accounts.csv: a stale Simulation=DISCONNECTED does not refuse its entry",
              ad._all_disconnected(ad.connections()) is False)
        ad_sim = mk("Sim101")
        check("6b. Sim101 keeps the old rule (every file DISCONNECTED -> refused)", ad_sim._all_disconnected(ad_sim.connections()) is True)
        folder(f, {"MFFU": "DISCONNECTED"}, [("MFFUEVAL50K123", now - 3600)])
        check("6c. MFFU account stale + every file DISCONNECTED -> refused (as before)", ad._all_disconnected(ad.connections()) is True)
        folder(f, {"MFFU": "CONNECTED"}, [])
        check("6d. a CONNECTED file -> never refused", ad._all_disconnected(ad.connections()) is False)
        check("6e. no connection file -> never refused (as before)", ad._all_disconnected({}) is False)
        # 7. PC health check, heartbeat outgoing summary, botctl probe
        folder(f, {"Simulation": "DISCONNECTED"}, [("MFFUEVAL50K123", now - 20)])
        c = ops_checks.check_nt_connection(ops_checks.nt_connections(f), now, f)
        check("7a. ops check: stale DISCONNECTED file + live MFFU account -> OK", c["level"] == ops_checks.OK, c)
        c = ops_checks.check_nt_connection({"MFFU Rithmic": "DISCONNECTED"}, now)
        check("7b. ops check without a folder: unchanged (DISCONNECTED -> BAD)", c["level"] == ops_checks.BAD, c)
        folder(f, {"Simulation": "CONNECTED"}, [("MFFUEVAL50K123", now - 20)])
        sm = nt_log.outgoing_summary(f)
        check("7c. heartbeat outgoing summary: connected + live account count + note",
              sm.get("connections") == ["Simulation=CONNECTED"] and sm.get("connected") is True and sm.get("live_accounts") == 1
              and "only" in (sm.get("note") or ""), sm)
        folder(f, {"Simulation": "CONNECTED", "MFFU_Rithmic": "CONNECTED"}, [])
        sm = nt_log.outgoing_summary(f)
        check("7c2. a connection name with '_' is listed (was counted as 'other': only Simulation showed)",
              sorted(sm.get("connections") or []) == ["MFFU_Rithmic=CONNECTED", "Simulation=CONNECTED"], sm)
        folder(f, {"Simulation": "CONNECTED"}, [("MFFUEVAL50K123", now - 20)])
        pr = botctl.folder_probe(f, now)
        check("7d. botctl folder probe: connected with its reasons", pr.get("connected") is True and "live account in accounts.csv" in pr.get("connected_via"), pr)
        # 8. (same QA pass) the bar reader drops a last line still being appended (no "\n" yet): "21000.5" cut to "2100"
        # would otherwise be read as a valid close
        p = os.path.join(f, "le_feed", "MNQ_1m.csv")
        with open(p, "w", newline="") as fh:
            fh.write("time,open,high,low,close,volume\n1793668020,21000,21001,20999,21000.5,5\n1793668080,21000.5,21001,20999.75,2100")
        df = nt.NinjaTraderBars(f).load(p)
        check("8a. torn last line dropped (only the whole bar is read)", list(df["time"]) == [1793668020] and df["close"].iloc[-1] == 21000.5,
              df.to_dict("records"))
        with open(p, "a", newline="") as fh:
            fh.write("0.25,7\n")
        df = nt.NinjaTraderBars(f).load(p)
        check("8b. once the line is whole it is read", list(df["time"]) == [1793668020, 1793668080] and df["close"].iloc[-1] == 21000.25,
              df.to_dict("records"))
        with open(p, "w", newline="") as fh:
            fh.write("time,open,high,low,close,volume\r\n1793668020,21000,21001,20999,21000.5,5\r\n")
        check("8c. Windows line ends read as before", list(nt.NinjaTraderBars(f).load(p)["time"]) == [1793668020])
        # 9. LE_Feed installed (NO_CHART_MODE.bat copied it) but never started: the health line says so
        folder(f, {}, None)
        check("9a. no add-on, no status: chart mode (None)", nt.feed_addon_line(f, now) is None)
        os.makedirs(os.path.join(f, "bin", "Custom", "AddOns"))
        open(os.path.join(f, "bin", "Custom", "AddOns", "LE_Feed.cs"), "w").close()
        check("9b. add-on installed, no status file: 'installed but has not started'", nt.feed_addon_line(f, now) == nt.ADDON_NOT_STARTED)
        with open(os.path.join(f, "le_feed", "le_feed_status.txt"), "w") as fh:
            fh.write(f"{now - 5},source=addon,instruments=MNQ 12-26,last_1m=,resubs=0,connected=1,started={now - 5}\n")
        check("9c. once it writes its status: the usual line", nt.feed_addon_line(f, now) == "bars from LE_Feed (no chart), 0 re-subscribes (MNQ 12-26)",
              nt.feed_addon_line(f, now))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
