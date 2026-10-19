"""Bot health: the heartbeat's "health" block (engine/accounts.pc_health), the cloud's verdict on it (accounts.verdict:
TRADING YOUR EVAL / ON SIM / PAPER ONLY / DISABLED / PC SILENT / FEED STALE / CAN'T CONFIRM) and the hourly phone push
(accounts.alert_due + verdict_notice). Read-only, no secrets.

  python -X utf8 -m tests.test_health
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

from engine import accounts, heartbeat
from tests.test_accounts import fake_bot, ts


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_health_")
    results = []

    def check(name, cond, info=""):
        results.append(bool(cond))
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""))

    old_env = os.environ.get("NINJATRADER_LIVE")
    try:
        os.environ["NINJATRADER_LIVE"] = "1"
        bot, now = fake_bot(tmp)                       # 2026-10-20 09:40 ET, MFFUEVAL123 (live), short open
        bot.cfg.update(armed=True, data_source="ninjatrader", tf="5m")
        bot.started_at, bot.last_poll, bot.errors = now - 7200, now - 20, 2
        bot.health.update(data_source="ninjatrader", last_bar_t=now - 600, last_1m_bar_t=now - 110, last_ok_poll=now - 20,
                          market_open=True, last_error=r"poll failed: C:\Users\Owner\Documents\x.csv locked", last_error_t=now - 900)
        bot.adapter.connections = lambda: {"Rithmic": "CONNECTED"}
        bot.adapter.folder_status = lambda: {"incoming": True, "outgoing": True, "folder": r"C:\Users\Owner\Documents\NinjaTrader 8"}
        bot.adapter.last_error = None
        sig = {"t": ts(2026, 10, 20, 8, 25), "day": "2026-10-20", "dir": -1, "limit_px": 25070.0, "stop_px": 25110.0,
               "target_px": 24900.0, "risk_pts": 40.0, "rr": 4.25, "swept": ["pdh"], "status": "filled"}
        bot.state.update(model_state="LIT: IN TRADE SHORT @ 25,070.00 | stop 25,110.00 | target 24,900.00", price=25040.0,
                         lit={"signals_today": [sig]}, day_trades=1)
        h = accounts.pc_health(bot, now=now)
        blob = json.dumps(h)
        check("health: no error", "error" not in h, h.get("error"))
        a = h["account"]
        check("account: name, LIVE, enabled, armed, live lock bool",
              a["name"] == "MFFUEVAL123" and a["is_live"] and a["label"] == "LIVE" and a["enabled"] and a["armed"] and a["live_lock"] is True, a)
        check("feed: ninjatrader, 1m age 50 s, 5m age 300 s", h["feed"]["used"] == "ninjatrader" and h["feed"]["age_1m_s"] == 50
              and h["feed"]["age_5m_s"] == 300, h["feed"])
        check("poll: last poll 20 s ago, 2 errors, error text without the path",
              h["poll"]["age_s"] == 20 and h["poll"]["errors"] == 2 and "Users" not in (h["poll"]["last_error"] or "") and "<path>" in h["poll"]["last_error"], h["poll"])
        check("NinjaTrader: connected, 1 open bracket", h["nt"]["connected"] is True and h["nt"]["open_brackets"] == 1, h.get("nt"))
        check("LIT: in trade, 1 setup today, last = SHORT PDH", h["lit"]["stage"] == "trade" and h["lit"]["setups_today"] == 1
              and h["lit"]["last_setup"]["side"] == "SHORT" and "PDH" in h["lit"]["last_setup"]["level"].upper(), h["lit"])
        check("orders today: 4 sent, 2 entries", h["orders"]["today"] == 4 and h["orders"]["entries_today"] == 2, h["orders"])
        check("uptime: bot 2 h", h["uptime"]["bot_s"] == 7200 and h["uptime"]["server_s"] >= 0, h["uptime"])
        check("no secrets: no webhook, confirm phrase, paths, env value", "SECRET" not in blob and "I UNDERSTAND" not in blob
              and "Users" not in blob and "NinjaTrader 8" not in blob, blob[:300])
        check("health block is small (< 4 KB)", len(blob) < 4096, len(blob))
        os.environ.pop("NINJATRADER_LIVE", None)
        check("live lock off reports False", accounts.pc_health(bot, now=now)["account"]["live_lock"] is False)

        # stages
        def stage(st):
            return accounts._lit_stage(st)["stage"]
        check("stage: watching levels", stage({"model_state": "LIT: watching for a sweep + inducement + CISD"}) == "levels")
        check("stage: limit armed", stage({"model_state": "LIT: SHORT limit armed", "setups": {"short": {"limit": 1}}}) == "limit")
        check("stage: limit tapped -> 1m CISD", stage({"setups": {"short": {"tapped_t": 5}}}) == "cisd1m")
        check("stage: entering -> trade", stage({"enter_now": {"entry_t": 1}}) == "trade")
        check("stage: done for today", stage({"model_state": "LIT: done for today (STOP)", "day_trades": 1}) == "done")
        check("stage: market closed", stage({"model_state": "LIT: market closed (next session 18:00 ET)"}) == "closed")

        # the heartbeat carries it; a broken bot never breaks it
        pl = heartbeat.Heartbeat(bot).payload()
        check("heartbeat payload carries health", isinstance(pl.get("health"), dict) and pl["health"].get("v") == 1, list(pl))
        broken = SimpleNamespace(cfg=None, state=None, running=True, ledger=None, health=None, adapter=None)
        bh = heartbeat.Heartbeat(broken).payload().get("health")
        check("broken bot: health degrades, never raises", isinstance(bh, dict), bh)

        # verdicts
        t9 = ts(2026, 10, 20, 9, 40)
        good = {"present": True, "t": t9 - 120, "running": True, "adapter": "ninjatrader", "every_s": 300, "host": "DESKTOP", "health": h}

        def V(pc, at=t9):
            return accounts.verdict(pc, at)

        def mut(fn):
            pc = copy.deepcopy(good)
            fn(pc)
            return pc
        v = V(good)
        check("green: TRADING YOUR EVAL", v["code"] == "TRADING" and v["label"] == "TRADING YOUR EVAL" and v["level"] == "good", v)
        check("silent: heartbeat 25 min old", V(mut(lambda p: p.update(t=t9 - 1500)))["code"] == "SILENT")
        check("silent: no heartbeat at all", V({"present": False})["label"] == "PC SILENT")
        check("disabled: bot stopped", V(mut(lambda p: p["health"].update(running=False)))["label"] == "DISABLED: bot stopped")
        check("disabled: kill switch", V(mut(lambda p: p["health"].update(kill=True)))["label"] == "DISABLED: kill switch on")
        check("paper only", V(mut(lambda p: p["health"]["account"].update(adapter="paper", is_live=False, label="PAPER")))["code"] == "PAPER")
        check("on sim", V(mut(lambda p: p["health"]["account"].update(name="Sim101", is_live=False, label="SIM")))["label"] == "ON SIM")
        dv = V(mut(lambda p: p["health"]["account"].update(enabled=False, disabled="LIVE account X refused: start the server with NINJATRADER_LIVE=1")))
        check("disabled: the adapter's reason", dv["code"] == "DISABLED" and "NINJATRADER_LIVE" in dv["label"], dv)
        check("disabled: NinjaTrader disconnected", V(mut(lambda p: p["health"]["nt"].update(connected=False)))["label"] == "DISABLED: NinjaTrader disconnected")
        stale = mut(lambda p: p["health"]["feed"].update(age_1m_s=600))
        check("feed stale in session (1m bar 10 min old)", V(stale)["label"] == "FEED STALE")
        check("feed not judged outside the session (17:30 ET)", V({**stale, "t": ts(2026, 10, 20, 17, 28)}, ts(2026, 10, 20, 17, 30))["code"] == "TRADING")
        check("feed not judged when the PC says market closed", V(mut(lambda p: p["health"]["feed"].update(age_1m_s=600, market_open=False)))["code"] == "TRADING")
        check("feed stale: no poll for 6 min", V(mut(lambda p: p["health"]["poll"].update(age_s=360)))["code"] == "FEED")
        check("old PC bot (no health block): CAN'T CONFIRM",
              V({"present": True, "t": t9 - 60, "running": True, "adapter": "ninjatrader", "every_s": 300})["code"] == "OLD")
        check("old PC bot on paper: PAPER ONLY", V({"present": True, "t": t9 - 60, "running": True, "adapter": "paper"})["code"] == "PAPER")

        # the alert throttle: once per reason per hour, 01:50-15:55 ET weekdays, never when green
        sim = V(mut(lambda p: p["health"]["account"].update(name="Sim101", is_live=False, label="SIM")))
        due, prev = accounts.alert_due(sim, t9, {})
        check("alert: first ON SIM pushes", due and "ON SIM" in prev)
        due2, prev = accounts.alert_due(sim, t9 + 1800, prev)
        check("alert: same reason within the hour is quiet", not due2)
        fv = V(stale)
        due3, prev = accounts.alert_due(fv, t9 + 1900, prev)
        check("alert: a different reason pushes at once", due3)
        due4, prev = accounts.alert_due(sim, t9 + 3601, prev)
        check("alert: the same reason again after an hour", due4)
        check("alert: green never pushes", not accounts.alert_due(v, t9, {})[0])
        check("alert: 01:45 ET is quiet, 01:50 pushes", not accounts.alert_due(sim, ts(2026, 10, 20, 1, 45), {})[0]
              and accounts.alert_due(sim, ts(2026, 10, 20, 1, 50), {})[0])
        check("alert: 16:00 ET is quiet", not accounts.alert_due(sim, ts(2026, 10, 20, 16, 0), {})[0])
        check("alert: Saturday is quiet", not accounts.alert_due(sim, ts(2026, 10, 24, 10, 0), {})[0])
        n = accounts.verdict_notice(sim, good, t9)
        check("notice: kind pc (always pushed), title names the reason", n["kind"] == "pc" and n["title"] == "Bot NOT trading your eval: ON SIM"
              and n["url"] == "#/accounts", n)
        check("notice: open position called out", "POSITION IS OPEN" in n["body"], n["body"])
        from engine import push as _push
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "cloud_monitor.py"), encoding="utf-8").read()
        check("cloud monitor pushes kind pc", '"pc") or push.extra_on()' in src and "verdict_notice" in src)
        check("push wire keeps title / body", json.loads(_push.wire(n))["title"] == n["title"])
    finally:
        if old_env is None:
            os.environ.pop("NINJATRADER_LIVE", None)
        else:
            os.environ["NINJATRADER_LIVE"] = old_env
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"health: {sum(results)}/{len(results)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
