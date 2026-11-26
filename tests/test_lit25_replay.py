"""Sim replay of the lit25 switch (LIT also on ATLAS's FUNDED 25K, engine/lit25.py): the REAL LiveBot over real 2026 sessions,
fake NinjaTrader (engine/ninjatrader._FakeNT on a temp folder; Sim101 = Zlarior's 50K, Sim107 = ATLAS's funded 25K), polled on
the PC bot's schedule. Nothing real is read, written or armed (the start cfg "lit25" / "account_b" drive the harness).

    python -X utf8 -m tests.test_lit25_replay             # 3 sessions ON + the same sessions OFF (~6-10 min)
    python -X utf8 -m tests.test_lit25_replay --days 2026-09-02,2026-09-04 [--restart-days 2026-09-09]
    + (red team #18) restarts of the bot mid-trade with ONE lane open, until both cases ran: LIT open -> restart -> ATLAS stays
      blocked; ATLAS open -> restart -> LIT's entry closes ATLAS first

Checks (ON): the LIT lane + SharedAtlas exist on Sim107; NEVER both lanes holding a position on Sim107 at the same poll and no
entry of either lane while the other's entry is open (ledger order); every LIT-lane entry is one of LIT's own entries of that
day (the lane mirrors LIT, never invents a trade); ATLAS never enters while LIT's lane holds; no live-loop error; at least one
LIT-lane and one ATLAS trade over the run (not vacuous). (OFF): no lane, ATLAS is the plain account B, nothing on Sim107
but ATLAS. BLITZ / the Rapid are not configured (untouched).
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import lit25  # noqa: E402
from engine import live  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402
from tests import test_combo_50k as T5  # noqa: E402
from tests import test_second_route as TR  # noqa: E402
from tests.test_second_route import Harness, at, hm  # noqa: E402

RESULTS = TR.RESULTS
check = TR.check
NAME = "Sim107"
DAYS = ["2026-09-09", "2026-10-06", "2026-10-07"]           # days with LIT + 2-3 ATLAS research trades
FUNDED_B = {"account": NAME, "plan": "builder25k", "eval_start": "2026-08-03", "sizing": "need", "stage": "funded",
            "funded_start": "2026-09-01", "payouts": {}, "eval_account": "Sim102", "armed": True,
            "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]}


def lane_of(b):
    return next((a for a in (getattr(b.accts, "accounts", None) or []) if a.spec.get("lane") == "lit25"), None)


def day_bot(H, tag, day, on, fake=None, start_t=None):
    d = os.path.join(H.tmp, tag, day)
    folder = os.path.join(d, "NinjaTrader 8")
    fake = fake or nt._FakeNT(folder, price=25000.0)     # a restart keeps the same NinjaTrader folder (positions, orders)
    clock = H.clock

    def nt_sleep(s_, fake=fake):
        fake.process()
        clock.base += s_

    def fac(_x, cfg):
        if cfg.get("adapter") != "ninjatrader":
            return live.ADAPTERS[cfg["adapter"]](cfg)
        ad = nt.NinjaTraderAdapter({**cfg, "nt_folder": folder}, clock=clock)
        ad._sleep = nt_sleep
        ad._alert_fn = lambda *a_, **kw: None
        return ad
    MA.ADAPTER_FACTORY = fac
    AB.ADAPTER_FACTORY = fac
    b, fake = H.bot(os.path.join(tag, day), [], start_t or at(day, 1, 45), fake=fake,
                    cfg_extra={"account_b": dict(FUNDED_B), "lit25": {"on": bool(on)}, "accounts_parallel": False, "account_c": None,
                               "fleet": None, "rapid": None, "eval_start": "2026-08-03"})
    return b, fake


def entries(obj, day):
    out = []
    for e in getattr(obj, "ledger", None) or []:
        if e.get("side") in ("buy", "sell") and e.get("entry_t") and live.trading_day(int(e["entry_t"])) == day \
                and (e.get("result") or {}).get("ok") is not False:
            out.append(int(e["entry_t"]))
    return out


def order_bad(objs):
    ev = []
    for o in objs:
        for r in getattr(o, "ledger", None) or []:
            if r.get("side") in ("buy", "sell", "exit") and (r.get("result") or {}).get("ok") is not False:
                ev.append((int(r["t"]), 0 if r["side"] == "exit" else 1, r["side"], r.get("entry_t")))
    ev.sort()
    open_, bad = None, []
    for t, _, side, et_ in ev:
        if side in ("buy", "sell"):
            if open_ is not None:
                bad.append((hm(t), "entry while", hm(open_)))
            open_ = et_
        elif et_ == open_:
            open_ = None
    return bad


RESTART_DAYS = ["2026-09-09", "2026-10-06", "2026-10-07", "2026-09-18", "2026-10-13", "2026-09-04", "2026-10-02"]


def restart_day(H, day, keys, seen):
    """Red team #18: the PC bot RESTARTED mid-trade with ONE lane open on the shared funded 25K. The bot is stopped at the first
    poll where LIT's lane or ATLAS holds a position and started again on the same state file + the same NinjaTrader folder
    (positions and brackets survive), then the session goes on. seen = {"lit": n, "atlas_then_lit": n} coverage."""
    wakes = H.times(day, keys)
    b, fake = day_bot(H, "rs", day, True)
    errs, both, restarted = [], [], None

    def watch(bot, w):
        l_, a_ = lane_of(bot), bot.acct_b
        if l_ is not None and a_ is not None and l_.open_t is not None and getattr(a_, "open_t", None) is not None:
            both.append((hm(int(bot.clock())), hm(int(l_.open_t)), hm(int(a_.open_t))))
    for i, w in enumerate(wakes):
        H.run(b, fake, [w], errs, on_poll=watch)
        if restarted is None:
            l_, a_ = lane_of(b), b.acct_b
            who = "lit" if (l_ is not None and l_.open_t is not None) else ("atlas" if getattr(a_, "open_t", None) is not None else None)
            if who:
                open_t = int(l_.open_t) if who == "lit" else int(a_.open_t)
                b.stop()
                b, fake = day_bot(H, "rs", day, True, fake=fake, start_t=int(w) + 30)
                l2, a2 = lane_of(b), b.acct_b
                kept = (l2 is not None and l2.open_t is not None and int(l2.open_t) == open_t) if who == "lit" else \
                    (a2 is not None and getattr(a2, "open_t", None) is not None and int(a2.open_t) == open_t)
                check(f"{day} restart with {'LIT' if who == 'lit' else 'ATLAS'} open ({hm(open_t)}): the open trade is known again after the restart",
                      kept, (who, hm(open_t), l2 and l2.open_t, getattr(a2, "open_t", None)))
                restarted = (who, int(w), open_t)
    L, A = lane_of(b), b.acct_b
    objs = [o for o in (L, A) if o is not None]
    check(f"{day} restart: never both lanes holding at one poll, no entry while the other is open (before + after the restart)",
          not both and not order_bad(objs), (both[:3], order_bad(objs)[:3]))
    check(f"{day} restart: no live-loop error", not errs, errs[:3])
    if restarted:
        who, w_r, open_t = restarted
        if who == "lit":
            seen["lit"] += 1
            a_after = [t for t in entries(A, day) if t >= w_r] if A is not None else []
            lane_exit = [int(r["t"]) for r in (L.ledger if L else []) if r.get("side") == "exit" and r.get("entry_t") == open_t]
            ok = all(lane_exit and t >= min(lane_exit) for t in a_after)
            check(f"{day} restart with LIT open: ATLAS stays blocked until LIT's trade is out ({len(a_after)} ATLAS entries after)",
                  ok, (a_after, lane_exit))
        else:
            lane_after = [t for t in (entries(L, day) if L else []) if t >= w_r]
            a_exit = [(int(r["t"]), r.get("reason")) for r in (A.ledger if A else []) if r.get("side") == "exit" and r.get("entry_t") == open_t]
            if lane_after:
                seen["atlas_then_lit"] += 1
                first_lane = min(int(r["t"]) for r in L.ledger if r.get("side") in ("buy", "sell") and r.get("entry_t") in lane_after)
                ok = bool(a_exit) and a_exit[0][0] <= first_lane
                check(f"{day} restart with ATLAS open, then LIT enters: ATLAS is closed first ({a_exit[:1]}), then LIT's lane routes",
                      ok, (a_exit, hm(first_lane)))
            else:
                seen["atlas_only"] = seen.get("atlas_only", 0) + 1
    b.stop()
    print(f"   restart {day}: {restarted and restarted[0]} open at {restarted and hm(restarted[2])}, coverage {seen}", flush=True)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    days = argv[argv.index("--days") + 1].split(",") if "--days" in argv else DAYS
    t0 = time.time()
    ref = TR.Ref()
    H = Harness(ref, lm_extra={"lit_sizing": T5.lit_sizing()})
    keys = list(getattr(ref, "sec", {}) or {})
    n_lane = n_atlas = n_lit = 0
    try:
        for day in days:
            wakes = H.times(day, keys)
            # ---- ON
            b, fake = day_bot(H, "on", day, True)
            L, A = lane_of(b), b.acct_b
            ok_cfg = L is not None and isinstance(A, lit25.SharedAtlas) and L.spec.get("nt_account") == NAME == getattr(A, "name", None)
            both, errs = [], []

            def on_poll(bot, w, both=both):
                l_, a_ = lane_of(bot), bot.acct_b
                if l_ is not None and a_ is not None and l_.open_t is not None and getattr(a_, "open_t", None) is not None:
                    both.append((hm(int(bot.clock())), hm(int(l_.open_t)), hm(int(a_.open_t))))
            H.run(b, fake, wakes, errs, on_poll=on_poll)
            lit_e, lane_e, atl_e = entries(b, day), entries(L, day) if L else [], entries(A, day)
            n_lit, n_lane, n_atlas = n_lit + len(lit_e), n_lane + len(lane_e), n_atlas + len(atl_e)
            check(f"{day} ON: LIT lane + SharedAtlas on {NAME}", ok_cfg, (L and L.problem, getattr(A, "problem", None), type(A).__name__))
            check(f"{day} ON: the lane sizes at ATLAS's 40% funded room (owner's FUNDED_ON), not the preset's 60%",
                  L is not None and ((L.spec.get("lit_sizing") or {}).get("funded") or {}).get("pct") == 0.4,
                  L and L.spec.get("lit_sizing"))
            check(f"{day} ON: never both lanes holding on {NAME} at one poll; no entry while the other is open (ledger order)",
                  not both and not order_bad([o for o in (L, A) if o is not None]), (both[:3], order_bad([o for o in (L, A) if o is not None])[:3]))
            check(f"{day} ON: every LIT-lane entry is one of LIT's own entries ({len(lane_e)} lane / {len(lit_e)} LIT)",
                  set(lane_e) <= set(lit_e), sorted(set(lane_e) - set(lit_e))[:3])
            check(f"{day} ON: no live-loop error", not errs, errs[:3])
            b.stop()
            # ---- OFF (today's bot)
            b0, fake0 = day_bot(H, "off", day, False)
            errs0 = []
            H.run(b0, fake0, wakes, errs0)
            check(f"{day} OFF: no lane, ATLAS is the plain account B, nothing on {NAME} but ATLAS",
                  lane_of(b0) is None and type(b0.acct_b) is AB.AccountB and not errs0, (type(b0.acct_b).__name__, errs0[:2]))
            b0.stop()
            n_ref = sum(len(ref.sec[k].get(day, [])) for k in keys)
            print(f"   {day}: LIT {len(lit_e)}, LIT lane {len(lane_e)}, ATLAS {len(atl_e)} entries (research ATLAS {n_ref}), "
                  f"{time.time() - t0:.0f} s", flush=True)
            if n_ref and not atl_e:
                why = [x["text"] for x in list(getattr(A, "log", None) or b.log) if "ATLAS" in x.get("text", "") or "skip" in x.get("text", "")]
                print("     ATLAS not routed: " + " | ".join(why[-4:])[:600], flush=True)
        check(f"not vacuous: >= 1 LIT-lane entry and >= 1 ATLAS entry over {len(days)} sessions (lane {n_lane}, ATLAS {n_atlas}, LIT {n_lit})",
              n_lane >= 1 and n_atlas >= 1)
        # ---- red team #18: restarts mid-trade (until both cases are covered)
        seen = {"lit": 0, "atlas_then_lit": 0}
        for day in (RESTART_DAYS if "--restart-days" not in argv else argv[argv.index("--restart-days") + 1].split(",")):
            if seen["lit"] and seen["atlas_then_lit"]:
                break
            restart_day(H, day, keys, seen)
        check(f"restart coverage: a restart with LIT open AND a restart with ATLAS open followed by a LIT entry ({seen})",
              seen["lit"] >= 1 and seen["atlas_then_lit"] >= 1)
    finally:
        MA.ADAPTER_FACTORY = None
        AB.ADAPTER_FACTORY = None
        H.close()
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n_ok}/{len(RESULTS)} checks passed ({time.time() - t0:.0f} s)")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
