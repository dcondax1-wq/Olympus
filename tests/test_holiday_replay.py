"""Holiday replay on Sim adapters (night-hol 2026-11-17): every routed lane is flat before each CME early close and takes no
entry inside the no-entry window. MFFU (research/lit/mffu_rules.json builder_50k.eval.holidays_early_close): MFFU does NOT
auto-flatten at a CME half-day halt; a position still open at the halt = the account fails.

    python -X utf8 -m tests.test_holiday_replay

Each lane's NinjaTrader adapter is built from that lane's OWN cfg builder (LIT main = the bot cfg, ATLAS account B
AccountB.adapter_cfg, the Rapid EOD's LIT lane multi_account.AccountRouter.adapter_cfg(rapid.lane_spec) + its ATLAS lane
RapidAtlas.adapter_cfg, an extra account, a fleet follower, a BLITZ router at flat_mod LAST_IN + 1) on a Sim account, against
the simulated NinjaTrader (engine.ninjatrader._FakeNT), minute by minute through:
  Thu 2026-11-26 Thanksgiving  halt 13:00 ET (12:00 CT): entries to 12:44, flat at 12:55
  Fri 2026-11-27               halt 13:15 ET (12:15 CT): entries to 12:59, flat at 13:10
  Thu 2026-12-24 Christmas Eve halt 13:15 ET (12:15 CT): entries to 12:59, flat at 13:10
  Fri 2026-12-25 / Fri 2027-01-01 closed: no entry; Thu 2026-12-31 full day: entry at 15:00 ok, flat at 15:55
For each: an entry 16 min before the halt is taken, one 15 min before is refused, the open trade is flat with no working
stop / target at halt - 5 min (not a minute earlier), and a position the bot did not open (a hand trade) on the same account
is closed too. Then the 7-day inactivity rule over the holiday weeks (engine/cme_calendar.idle_plan + the two warnings).
Temp dirs only.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(y, m, d, hh, mm=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def lane_cfgs(tmp, folder):
    """{lane: adapter cfg} from each lane's own builder, every one on its own Sim account."""
    from engine import account_b as AB, blitz, fleet, multi_account as MA, rapid
    bot_cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_account": "Sim101", "nt_folder": folder,
               "params": {"max_micros": 40, "flat_mod": 955}, "model": "lit", "model_params": {"window": [[120, 930]]},
               "nt_max_entries_day": 999}
    bot = types.SimpleNamespace(cfg=bot_cfg, state_path=os.path.join(tmp, "live_state.json"))
    out = {"LIT main (Zlarior)": {**bot_cfg, "nt_state_path": os.path.join(tmp, "nt_lit.json"),
                                  "nt_audit_log": os.path.join(tmp, "oif_lit.log")}}

    def acct_b(cls, name):
        b = object.__new__(cls)
        b.bot, b.name, b.rules, b.spec = bot, name, {"max_micros": 40}, {"armed": True}
        b.state_path = os.path.join(tmp, f"{cls.__name__}.json")
        return b.adapter_cfg()
    out["ATLAS account B"] = acct_b(AB.AccountB, "Sim102")
    router = object.__new__(MA.AccountRouter)
    router.bot, router.state_path = bot, os.path.join(tmp, "accounts_state.json")
    blk = {"account": "Sim103", "armed": True}
    lane = types.SimpleNamespace(id=rapid.LANE_ID, spec={**rapid.lane_spec(blk, bot_cfg), "adapter": "ninjatrader"},
                                 rules={"max_micros": 40})
    out["Rapid LIT lane"] = MA.AccountRouter.adapter_cfg(router, lane)
    out["Rapid ATLAS lane"] = acct_b(rapid.RapidAtlas, "Sim103")          # the same account as the Rapid LIT lane
    extra = types.SimpleNamespace(id="x2", spec={"adapter": "ninjatrader", "nt_account": "Sim104", "armed": True},
                                  rules={"max_micros": 40})
    out["extra account"] = MA.AccountRouter.adapter_cfg(router, extra)
    fl = object.__new__(fleet.Fleet)
    fl.bot, fl.state_path = bot, os.path.join(tmp, "fleet_state.json")
    fol = types.SimpleNamespace(id="f1", spec={"adapter": "ninjatrader", "nt_account": "Sim105", "armed": True}, profile={})
    out["fleet follower"] = fleet.Fleet.adapter_cfg(fl, fol)
    out["BLITZ router"] = {**bot_cfg, "nt_account": "Sim106", "params": {"max_micros": 40, "flat_mod": blitz.LAST_IN + 1},
                           "model": "blitz", "nt_session_from": 570, "nt_file_tag": "blz_",
                           "nt_state_path": os.path.join(tmp, "nt_blitz.json"), "nt_audit_log": os.path.join(tmp, "oif_blitz.log")}
    for c in out.values():
        c["nt_folder"], c["nt_max_entries_day"] = folder, 999
    return out


DAYS = [((2026, 11, 26), 13 * 60, "Thanksgiving Thu 11-26 (halt 13:00 ET)"),
        ((2026, 11, 27), 13 * 60 + 15, "Fri 11-27 (halt 13:15 ET)"),
        ((2026, 12, 24), 13 * 60 + 15, "Christmas Eve Thu 12-24 (halt 13:15 ET)")]


def t_replay(tmp):
    print("1. every routed lane on a Sim adapter: flat before each early close, no entry in the last 15 min", flush=True)
    from engine.ninjatrader import NinjaTraderAdapter, _FakeNT
    folder = os.path.join(tmp, "NinjaTrader 8")
    fake = _FakeNT(folder)
    now = [0.0]
    cfgs = lane_cfgs(tmp, folder)
    accts = {n: c["nt_account"] for n, c in cfgs.items()}
    check("7 lanes, each on a Sim account (the Rapid's two lanes share one), every cfg keeps the 15:55 flat + 02:00 LIT session",
          len(cfgs) == 7 and accts["Rapid LIT lane"] == accts["Rapid ATLAS lane"] == "Sim103"
          and all(int(c["params"]["flat_mod"]) == 955 for c in cfgs.values()), accts)

    def make(c):
        ad = NinjaTraderAdapter(c, clock=lambda: now[0])
        ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = lambda *a, **k: None
        return ad

    def side_of(ad):
        p = ad.position_for(ad._instruments()["micro"])
        return (p or {}).get("side", "FLAT")

    def working(acct):
        return [o for o in fake.orders.values() if o.get("account") == acct and o.get("state") in ("WORKING", "ACCEPTED")]

    for (y, m, d), halt, label in DAYS:
        bad = []
        for name, c in cfgs.items():
            ad = make(c)
            if ad.disabled:
                bad.append((name, "disabled", ad.disabled))
                continue
            entry_ok = halt - 16
            now[0] = ts(y, m, d, entry_ok // 60, entry_ok % 60) + 5
            r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": fake.price - 20, "target": fake.price + 60,
                         "entry": fake.price, "entry_t": ts(y, m, d, entry_ok // 60, entry_ok % 60)})
            if not r.get("ok") or side_of(ad) != "LONG":
                bad.append((name, f"entry at {entry_ok // 60:02d}:{entry_ok % 60:02d} not taken", r.get("error")))
                continue
            cut = halt - 15
            now[0] = ts(y, m, d, cut // 60, cut % 60) + 5
            r2 = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": fake.price - 20, "target": fake.price + 60,
                          "entry": fake.price, "entry_t": ts(y, m, d, cut // 60, cut % 60)})
            if r2.get("ok"):
                bad.append((name, "second entry at the cut accepted"))
            flat_at = None
            for mm in range(halt - 14, halt + 1):
                now[0] = ts(y, m, d, mm // 60, mm % 60) + 2
                ad.tick()
                fake.process()
                if side_of(ad) == "FLAT" and flat_at is None:
                    flat_at = mm
            if flat_at != halt - 5:
                bad.append((name, "flat at", flat_at, "want", halt - 5))
            if working(ad.account):
                bad.append((name, "orders still working at the halt", working(ad.account)))
            if ad.legs:
                bad.append((name, "legs left", [lg["status"] for lg in ad.legs]))
            # a hand trade on the same account (not the bot's): the account sweep closes it after the flat minute
            inst = ad._instruments()["micro"]
            fake.pos[(ad.account, inst)] = [1, fake.price]
            fake._write_pos(ad.account, inst)
            ad._flat_tries.clear()
            now[0] = ts(y, m, d, (halt - 4) // 60, (halt - 4) % 60) + 40
            ad.tick()
            fake.process()
            if side_of(ad) != "FLAT":
                bad.append((name, "hand position not closed before the halt"))
        check(f"{label}: all 7 lanes take an entry at halt - 16 min, refuse one at halt - 15, are flat with nothing working at "
              f"halt - 5 (not earlier), and close a hand position on the account before the halt", not bad, bad)

    bad = []
    for name, c in cfgs.items():
        ad = make(c)
        for day in ((2026, 12, 25), (2027, 1, 1)):
            now[0] = ts(*day, 10, 0)
            r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": fake.price - 20, "target": fake.price + 60,
                         "entry": fake.price, "entry_t": ts(*day, 10, 0)})
            if r.get("ok") or "holiday" not in str(r.get("error")):
                bad.append((name, day, r))
        now[0] = ts(2026, 12, 31, 15, 0)
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": fake.price - 20, "target": fake.price + 60,
                     "entry": fake.price, "entry_t": ts(2026, 12, 31, 15, 0)})
        if not r.get("ok"):
            bad.append((name, "12-31 15:00 refused", r.get("error")))
        flat_at = None
        for mm in range(15 * 60 + 50, 16 * 60 + 1):
            now[0] = ts(2026, 12, 31, mm // 60, mm % 60) + 2
            ad.tick()
            fake.process()
            if side_of(ad) == "FLAT" and flat_at is None:
                flat_at = mm
        if flat_at != 955:
            bad.append((name, "12-31 flat at", flat_at))
    check("Christmas Day 12-25 and New Year's Day 2027-01-01: every lane refuses an entry (CME holiday); New Year's Eve 12-31 is a "
          "full day: entry at 15:00 taken, flat at the normal 15:55", not bad, bad)
    check("simulated NinjaTrader saw only well-formed order lines", not fake.errors, fake.errors[:3])


def t_inactivity():
    print("2. MFFU 7-day inactivity over the holiday weeks", flush=True)
    from engine import cme_calendar as C, ops_checks as OC
    p = [C.idle_plan("2026-11-23", ts(2026, 11, 27, 8)), C.idle_plan("2026-12-21", ts(2026, 12, 24, 8)),
         C.idle_plan("2026-12-21", ts(2026, 12, 24, 14)), C.idle_plan("2026-12-28", ts(2026, 12, 31, 8)),
         C.idle_plan("2026-11-20", ts(2026, 11, 26, 8)), C.idle_plan("2026-11-16", ts(2026, 11, 20, 8)),
         C.idle_plan("2026-11-23", ts(2026, 11, 26, 8))]
    ok = (p[0]["squeeze"] and p[0]["last_session"] == "2026-11-27" and p[1]["squeeze"] and p[1]["last_session"] == "2026-12-24"
          and p[2]["sessions_left"] == 0 and p[3]["squeeze"] and p[3]["last_session"] == "2026-12-31"
          and p[4]["squeeze"] and p[4]["last_session"] == "2026-11-26"
          and not p[5]["squeeze"] and not p[6]["squeeze"] and p[6]["sessions_left"] == 2)
    check("idle_plan: last trade Mon 11-23 -> Fri 11-27 (half day) is the last session; Mon 12-21 -> Thu 12-24 (half day), none "
          "after its halt; Mon 12-28 -> Thu 12-31 (Jan 1 closed); a normal week is no squeeze", ok, p)
    # the two warnings: LIT's ops push (ops_checks) and ATLAS / Rapid ATLAS (account_b._idle_check) fire on the squeeze day
    view = {"is_live": True, "eval": {"status": "active", "start": "2026-11-02"}, "trades": [{"day": "2026-12-21"}]}
    a = OC.inactivity_notice(view, ts(2026, 12, 24, 8))                 # day 3, before: only from day 5 (Sat 12-26: too late)
    b = OC.inactivity_notice(view, ts(2026, 12, 22, 8))
    view2 = {**view, "trades": [{"day": "2026-11-16"}]}
    c = OC.inactivity_notice(view2, ts(2026, 11, 20, 8))                # normal week, day 4: unchanged (no push)
    d = OC.inactivity_notice(view2, ts(2026, 11, 21, 8))                # day 5: unchanged (push)
    check("LIT ops push: last trade Mon 12-21 -> warned Thu 12-24 morning (was Sat 12-26, after the last session), naming 12-24; "
          "not on Tue 12-22; a normal week unchanged (day 4 none, day 5 push)",
          a and "2026-12-24" in a.get("body", "") + str(a) and b is None and c is None and d is not None, (a, b, c, d))
    from engine import account_b as AB
    pushed = []
    fake = types.SimpleNamespace(idle_days=lambda now: 3, notified=[], name="Sim102", label="ATLAS", funded=lambda: False,
                                 eval_view=lambda now: {"status": "active"}, log=lambda *a: None,
                                 _push_text=lambda t, b, k: pushed.append(b))
    AB.AccountB._idle_check(fake, ts(2026, 12, 24, 8))
    AB.AccountB._idle_check(types.SimpleNamespace(**{**fake.__dict__, "notified": []}), ts(2026, 11, 19, 8))
    check("ATLAS / Rapid ATLAS (account_b._idle_check): 3 idle days on Thu 12-24 -> one push naming 12-24 as the last session; "
          "3 idle days on a normal Thursday -> none", len(pushed) == 1 and "2026-12-24" in pushed[0], pushed)


def main():
    tmp = tempfile.mkdtemp(prefix="le_holrep_")
    saved = {k: os.environ.pop(k, None) for k in ("NINJATRADER_LIVE", "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER")}
    try:
        t_replay(tmp)
        t_inactivity()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nholiday replay: {n_ok}/{len(RESULTS)} checks passed")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
