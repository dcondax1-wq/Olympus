"""The cloud monitor's upgrade shadow: LIT without t_check / scale_in / be_off as a second paper ledger (state lit_base) and
the with-vs-without comparison (state / data.json upgrades_live, README row). tools/upgrade_shadow.py + cloud_monitor.lit_base_step.

  python -X utf8 -m tests.test_upgrade_shadow
"""
from __future__ import annotations

import sys

from engine import lit
from engine import lit_live
from tools import cloud_monitor as cm
from tools import upgrade_shadow as us

UP = {"t_check": {"at": 15, "x": 0.3, "mfe": 0.5}, "scale_in": {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1},
      "be_off": 1.25}
T0 = 1_792_000_000


def _row(exit_, usd, qty=5, mult=1.0, day="2026-10-21"):
    return {"day": day, "entry": "10-21 05:00", "side": "SHORT", "exit": exit_, "usd": usd, "qty": qty, "mult": mult,
            "exit_ts": T0 + 3600, "R": 0.0}


def _trade(entry_t, exit_reason, pnl, qty=5):
    return {"entry_t": entry_t, "exit_t": entry_t + 1800, "dir": -1, "pnl_r": pnl / 500.0, "pnl": pnl, "qty": qty,
            "exit_reason": exit_reason, "trigger": "LIT", "risk_pts": 25.0, "entry": 20000.0, "stop": 20025.0,
            "target": 19900.0, "exit_price": 19990.0}


def main() -> int:
    checks = []

    def check(name, ok):
        checks.append(bool(ok))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")

    P = {**lit.DEFAULTS, **UP, "disp": 0.8}
    B = us.base_params(P)
    check("base params switch the three upgrades off and keep the rest",
          B["t_check"] is None and B["scale_in"] is None and B["be_off"] == 0.0 and B["disp"] == 0.8)
    check("upgrades_on lists what is on", us.upgrades_on(P) == ["t_check", "scale_in", "be_off"] and us.upgrades_on(B) == [])

    live = {T0: _row("CUT_T15", -260.0), T0 + 86400: _row("BE", 25.0), T0 + 2 * 86400: _row("TARGET", 1800.0, qty=6),
            T0 + 3 * 86400: _row("TARGET", 2000.0), T0 + 4 * 86400: _row("STOP", -500.0), T0 - 86400: _row("STOP", -900.0)}
    base = {T0: _row("STOP", -550.0), T0 + 86400: _row("BE", -14.0), T0 + 2 * 86400: _row("TARGET", 1500.0, qty=5),
            T0 + 3 * 86400: _row("TARGET", 1600.0), T0 + 5 * 86400: _row("TARGET", 700.0), T0 - 86400: _row("STOP", -900.0)}
    adds_trade = {"entry_t": T0 + 3 * 86400, "adds": [{"qty": 5, "pts": 40.0}]}
    u = us.compare(live, base, T0, ["t_check", "scale_in", "be_off"], live_trades=[adds_trade], scale_in_live=True)
    p = u["per_upgrade"]
    check("only trades from `since` count", u["trades_live"] == 5 and u["trades_base"] == 5)
    check("$ with vs without and the difference",
          u["usd_live"] == 3065.0 and u["usd_base"] == 3236.0 and u["delta"] == -171.0)
    check("t_check: the cut trade's saving", p["t_check"]["cuts"] == 1 and p["t_check"]["usd"] == 290.0)
    check("be_off: the BE trade's difference", p["be_off"]["n"] == 1 and p["be_off"]["usd"] == 39.0)
    check("scale_in: the adds' own $ (5 x (40 x $2 - $1.40))", p["scale_in"]["usd"] == 393.0 and "note" not in p["scale_in"])
    # other = size (+300) + the rest of the add trade (400 - 393 = 7) + only-live (-500) + only-base (-700)
    check("other: size, the add trade's rest and one-sided trades", u["other"]["n"] == 3 and u["other"]["usd"] == -893.0)
    tot = p["t_check"]["usd"] + p["be_off"]["usd"] + p["scale_in"]["usd"] + u["other"]["usd"]
    check("the parts add up to the difference", round(tot, 2) == u["delta"])
    u2 = us.compare(live, base, T0, ["t_check", "scale_in", "be_off"])
    check("no adds in the live loop: scale_in $0 with a note", p and u2["per_upgrade"]["scale_in"]["usd"] == 0.0
          and "note" in u2["per_upgrade"]["scale_in"])
    # merge2: the live loop carries adds (engine/lit_live._trade keeps them), so the attribution sees real live trades
    from engine import lit_live
    raw = {"entry_t": T0 + 3 * 86400, "exit_t": T0 + 3 * 86400 + 3600, "dir": 1, "entry_px": 20000.0, "exit_px": 20080.0,
           "stop_px": 19980.0, "target_px": 20080.0, "qty": 4, "pnl": 1000.0, "r": 4.0, "exit": "TARGET", "day": "d",
           "risk_pts": 20.0, "risk_usd": 160.0, "adds": [{"qty": 5, "pts": 40.0, "px": 20040.0}], "pts": 80.0, "qty_total": 9}
    lt = lit_live._trade(raw)
    check("live loop trades keep their adds and scale_in $ is attributed from them",
          lt.get("adds") and us.add_usd(lt, 1.0) == 393.0 and "ignores" not in str(u2["per_upgrade"]["scale_in"].get("note")))
    md = "\n".join(us.readme_rows(u))
    check("README section: with / without / added / per upgrade",
          "Upgrades live" in md and "-$171.00" in md and "15-minute check" in md and "cuts: 1" in md)
    check("README: an error is shown", "unavailable" in "\n".join(us.readme_rows({"error": "boom"})))
    s = us.seed({T0: _row("STOP", -1.0), T0 + 1: {**_row("OPEN", 0.0), "exit": "OPEN"}})
    check("seed copies finished rows only, marked seeded", list(s) == [T0] and s[T0]["seeded"])

    # lit_base_step: the base run gets LIT without the upgrades, builds its own ledger, never alerts
    lm = {"model": "lit", "lit": {**UP}, "lit_sizing": None, "sym": "NQ"}
    check("not LIT / no upgrade on -> no lit_base", cm.lit_base_step({"model": "engine"}, {}, None, T0, {}, {}, T0) == (None, None)
          and cm.lit_base_step({"model": "lit", "lit": {}}, {}, None, T0, {}, {}, T0) == (None, None))
    seen = {}
    real = lit_live.run

    def fake_run(df, P, **kw):
        seen["P"] = P
        return {"trades": [_trade(T0 + 600, "STOP", -550.0)], "state": {"model_state": "LIT: done", "position": None}, "events": []}
    lit_live.run = fake_run
    try:
        live_led = {T0 - 86400: _row("TARGET", 900.0), T0 + 600: _row("CUT_T15", -260.0)}
        st = {"lit_base": {"since": T0, "ledger": {}}}
        res = {"trades": [_trade(T0 + 600, "CUT_T15", -260.0)]}
        base, up = cm.lit_base_step(lm, st, None, T0 + 7200, live_led, res, T0 - 2 * 86400)
        check("the base run had no upgrades", seen["P"]["t_check"] is None and seen["P"]["scale_in"] is None
              and seen["P"]["be_off"] == 0.0)
        check("base ledger + comparison", base["since"] == T0 and len(base["ledger"]) == 1 and up["trades_base"] == 1
              and up["trades_live"] == 1 and up["per_upgrade"]["t_check"]["usd"] == 290.0)
        base1, _ = cm.lit_base_step(lm, {}, None, T0 + 7200, live_led, res, T0 - 2 * 86400)
        check("first run: seeded from the live ledger's finished rows, comparison from now",
              str(T0 - 86400) in base1["ledger"] and base1["since"] == T0 + 7200)

        def boom(*a, **k):
            raise RuntimeError("no bars")
        lit_live.run = boom
        b2, u3 = cm.lit_base_step(lm, st, None, T0, live_led, res, T0)
        check("an error never raises (reported in both blocks)", "error" in b2 and "error" in u3)
    finally:
        lit_live.run = real

    ok = all(checks)
    print(f"upgrade shadow: {sum(checks)}/{len(checks)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
