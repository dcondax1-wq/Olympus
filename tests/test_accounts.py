"""Accounts page: the heartbeat's "acct" block (engine/accounts.pc_activity) and the data.json "accounts" sections
(engine/accounts.build_accounts, tools/build_web_dashboard.py).

  python -X utf8 -m tests.test_accounts
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from engine import accounts, heartbeat
from engine.live import LiveBot

ET = ZoneInfo("America/New_York")


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def fake_bot(tmp, open_pos=True):
    now = ts(2026, 10, 20, 9, 40)
    b = LiveBot()
    b.state_path = os.path.join(tmp, "live_state.json")
    b.clock = lambda: now
    b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "eval_start": "2026-10-19", "eval_prior_pnl": -100,
             "webhook_url": "https://hooks.example/SECRET-TOKEN", "confirm": "I UNDERSTAND THIS IS LIVE", "model": "lit"}
    b._lit_sizing = {"eval_start": "2026-10-19", "eval_prior_pnl": -100}
    b._eval_prev = {"2026-10-19": 1450.0}
    b.running = True
    e1, e2 = ts(2026, 10, 20, 3, 5), ts(2026, 10, 20, 8, 35)
    oif = r"C:\Users\Owner\OneDrive\Documents\NinjaTrader 8\incoming\oif_LE_1.txt"
    b.ledger = [
        {"t": e1 + 3, "sym": "NQ", "side": "buy", "qty": 12, "stop": 24990.0, "target": 25150.0, "entry": 25020.0, "entry_t": e1,
         "result": {"ok": True, "adapter": "ninjatrader", "account": "MFFUEVAL123", "oif": oif,
                    "legs": [{"instrument": "MNQ 12-26", "qty": 12, "filled": 12, "fill_px": 25020.5, "ok": True, "stop": 24990.0,
                              "target": 25150.0, "stop_state": "ACCEPTED", "target_state": "WORKING"}]}},
        {"t": e1 + 1800, "sym": "NQ", "side": "modify", "qty": 12, "stop": 25020.5, "reason": "BE", "entry_t": e1,
         "result": {"ok": True, "stop": 25020.5}},
        {"t": e1 + 3600, "sym": "NQ", "side": "exit", "qty": 12, "reason": "BE", "pnl": -22.8, "entry_t": e1, "exit_t": e1 + 3600,
         "result": {"ok": False, "error": f"flatten sent, not confirmed: see {oif}"}},
    ]
    if open_pos:
        b.ledger.append({"t": e2 + 3, "sym": "NQ", "side": "sell", "qty": 8, "stop": 25110.0, "target": 24900.0, "entry": 25070.0,
                         "entry_t": e2, "result": {"ok": True, "legs": [{"filled": 8, "fill_px": 25069.75, "ok": True}]}})
        b._open_routed, b._open_qty = e2, 8
        b.state = {"position": {"entry_t": e2, "dir": -1, "qty": 9, "stop": 25110.0, "stop0": 25110.0, "target": 24900.0,
                                "entry": 25070.0, "risk_pts": 40.0, "be": False, "target_label": "VIX band low"}}
        b.adapter = SimpleNamespace(name="ninjatrader", account="MFFUEVAL123", env="live", disabled=None,
                                    legs=[{"entry_t": e2, "dir": -1, "fill_px": 25069.75, "stop": 25110.0, "target": 24900.0,
                                           "status": "protected", "filled": 8, "instrument": "MNQ 12-26", "stop0": 25110.0}])
    else:
        b.state = {"position": None}
        b.adapter = SimpleNamespace(name="ninjatrader", account="Sim101", env="demo", disabled=None, legs=[])
    return b, now


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_acct_")
    results = []

    def check(name, cond, info=""):
        results.append(bool(cond))
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""))

    try:
        jp = os.path.join(tmp, "journal.jsonl")
        with open(jp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"source": "pc", "key": "a", "day": "2026-10-19", "entry_t": ts(2026, 10, 19, 4, 10),
                                 "exit_t": ts(2026, 10, 19, 6, 0), "side": "LONG", "qty": 10, "entry_px": 24800, "stop_px": 24770,
                                 "target_px": 25040, "exit_px": 25040, "exit": "TARGET", "r": 8.0, "pnl": 1450.0, "risk_pts": 30,
                                 "swept": ["Asia low", "PDL"], "grade": "A", "cause": None}) + "\n")
            fh.write(json.dumps({"source": "cloud", "key": "b", "day": "2026-10-19", "entry_t": 1, "pnl": 5}) + "\n")
        bot, now = fake_bot(tmp)
        a = accounts.pc_activity(bot, now=now, journal_path=jp)
        blob = json.dumps(a)
        check("payload has no error", "error" not in a, a.get("error"))
        check("account name + LIVE label", a["account"]["name"] == "MFFUEVAL123" and a["account"]["label"] == "LIVE ACCOUNT", a.get("account"))
        p = a["position"] or {}
        check("open position: side, routed micros, broker fill, stop, target",
              p.get("side") == "SHORT" and p.get("qty") == 8 and p.get("entry") == 25069.75 and p.get("stop") == 25110.0 and p.get("target") == 24900.0, p)
        check("today's orders: entry, BE move, exit", [o["side"] for o in a["orders"]] == ["buy", "modify", "exit", "sell"], [o["side"] for o in a["orders"]])
        check("entry fill read from the broker legs", a["orders"][0].get("fill_px") == 25020.5 and a["orders"][0].get("filled") == 12, a["orders"][0])
        check("closed trades: journal (pc only) + today's ledger", len(a["trades"]) == 2 and a["trades"][0].get("swept") == ["Asia low", "PDL"], a["trades"])
        check("eval days carry the prior P&L and today", a["eval"]["days"].get("0000-00-00") == -100 and a["eval"]["days"].get("2026-10-20") == -22.8, a["eval"])
        check("no secrets / paths in the payload", "SECRET" not in blob and "I UNDERSTAND" not in blob and "Users" not in blob and "oif" not in blob.lower(), blob[:300])
        check("payload under 48 KB", len(blob) < accounts.MAX_BYTES, len(blob))
        big = {"v": 1, "trades": [{"x": "y" * 900}] * 200, "orders": [], "eval": {"days": {}}}
        check("fit() trims an oversized payload", len(json.dumps(accounts.fit(big))) < accounts.MAX_BYTES)
        # the heartbeat carries it, and a broken bot never breaks the heartbeat
        hb = heartbeat.Heartbeat(bot)
        pl = hb.payload()
        check("heartbeat payload carries acct", isinstance(pl.get("acct"), dict) and pl["acct"].get("v") == 1, list(pl))
        broken = SimpleNamespace(cfg={"adapter": "paper"}, state={}, running=True, ledger=None)
        broken.eval_days = lambda: 1 / 0
        check("broken bot: acct degrades, never raises", isinstance(heartbeat.Heartbeat(broken).payload().get("acct"), dict))
        flat_bot, _ = fake_bot(tmp, open_pos=False)
        fa = accounts.pc_activity(flat_bot, now=now, journal_path=jp)
        check("flat Sim account: no position, SIM label", fa["position"] is None and fa["account"]["label"] == "SIM", fa.get("account"))

        # cloud side: data.json sections
        lm = json.load(open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "live_model.json"), encoding="utf-8"))
        state = {"last_run": now, "pc": {"present": True, "t": now - 120, "age_s": 120, "silent": False, "running": True,
                                         "adapter": "ninjatrader", "host": "SURFACE", "acct": a},
                 "ledger": {str(ts(2026, 10, 19, 4, 10)): {"day": "2026-10-19", "side": "LONG", "exit": "TARGET", "R": 8.0, "usd": 1400.0,
                                                           "qty": 10, "exit_ts": ts(2026, 10, 19, 6, 0), "taken": True, "entry_px": 24800}},
                 "events": [], "position": None}
        secs = accounts.build_accounts(state, lm, now=now)
        check("one section per account + Paper (cloud)", [s["id"] for s in secs] == ["mffu50k_eval", "cloud_paper"], [s.get("id") for s in secs])
        ev = secs[0]["eval"]
        check("eval: $49,900 start + $1,450 - $22.80, session 2 of 10",
              abs(ev["balance"] - (50000 - 100 + 1450 - 22.8)) < 0.01 and ev["session"] == 2 and ev["sessions"] == 10, ev)
        check("eval: floor trails the EOD high ($49,350), daily loss used $22.80",
              ev["floor"] == 49350.0 and ev["dll_used"] == 22.8, (ev["floor"], ev["dll_used"]))
        check("PC section: LIVE badge, connected, position", secs[0]["badge"] == "LIVE" and secs[0]["conn"]["connected"] and secs[0]["position"]["side"] == "SHORT")
        check("stats computed", secs[0]["stats"]["n"] == 2 and secs[0]["stats"]["wins"] == 1, secs[0]["stats"])
        check("cloud paper section from the ledger", secs[1]["badge"] == "PAPER" and secs[1]["stats"]["n"] == 1, secs[1].get("stats"))
        old = accounts.build_accounts({"last_run": now, "pc": {"present": True, "t": now - 60}}, lm, now=now)
        check("old heartbeat (no acct): section still renders, flagged, and shows NO account numbers (display truth 2026-11-20: the eval built "
          "from eval_prior_pnl alone showed $49,900 under the real id while the account was $49,192.78)",
          old[0]["conn"]["has_detail"] is False and old[0]["eval"] is None and old[0]["pnl"] is None and old[0]["no_pc_numbers"] is True
          and old[0]["badge"] is None, old[0].get("eval"))
        cfg2 = accounts.accounts_cfg({"accounts": [{"id": "a"}, {"id": "b", "name": "B"}]})
        check("accounts list from live_model.json", [x["id"] for x in cfg2] == ["a", "b"] and accounts.accounts_cfg({})[0]["id"] == "mffu50k_eval")

        # the site builder puts the sections in data.json and keeps the raw block out of live.pc
        sp = os.path.join(tmp, "state.json")
        json.dump(state, open(sp, "w", encoding="utf-8"))
        from tools import build_web_dashboard as bwd
        out = os.path.join(tmp, "site")
        import contextlib
        import io
        # night-seedata 2026-11-23: build() refreshes the tracked tools/web_hub_snapshot.json on a machine with research files; a test
        # writes a temp copy instead, so a test run never dirties the repo
        real_snap = bwd.HUB_SNAPSHOT
        bwd.HUB_SNAPSHOT = os.path.join(tmp, "web_hub_snapshot.json")
        if os.path.isfile(real_snap):
            shutil.copyfile(real_snap, bwd.HUB_SNAPSHOT)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                bwd.build(sp, None, out)
        finally:
            bwd.HUB_SNAPSHOT = real_snap
        data = json.load(open(os.path.join(out, "data.json"), encoding="utf-8"))
        check("data.json has accounts", [s["id"] for s in data.get("accounts") or []] == ["mffu50k_eval", "cloud_paper"])
        check("data.json live.pc has no raw acct block", "acct" not in (data["live"].get("pc") or {}))
        check("data.json has no secrets", "SECRET-TOKEN" not in json.dumps(data["accounts"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"accounts: {sum(results)}/{len(results)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
