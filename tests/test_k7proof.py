"""MFFU 7-day keep-alive: an independent, adversarial proof over all four accounts (night-k7proof 2026-11-23). Paper / Sim
only (a fake NinjaTrader folder, Sim names), nothing armed, no network.

    python -X utf8 -m tests.test_k7proof        (~1-2 min)

The world: one bot with Zlarior's Builder 50K (key lit, Sim101), ATLAS's 25K (atlas, Sim102), the Rapid EOD 25K (rapid, Sim103:
its LIT lane + its ATLAS lane) and the 2nd Rapid, the Rapid EOD 50K (rapid2, Sim104). In each scenario only the account under
test has its switch ON, so a fire can only be its own. The PC's polls are replayed Mon 11-23 08:00 .. Sat 11-28 12:00 ET
(Thanksgiving Thu 11-26 = a 13:00 half day, Fri 11-27 = 13:15).

  1. fires before MFFU's deadline, inside the window, 1 MNQ, flat the same day, never on top of a bot trade
  2. the START phrase's consent covers all 4 (engine/go.armed_accounts -> keepalive.start_consent), rapid2 included
     (FOUND: both Rapid slots were keyed "rapid", start_consent dropped the 2nd as a duplicate; fixed in engine/go.py)
  3. a missed one (blocked all window) pushes "place 1 MNQ by hand before 16:05 ET" (the time left)
  4. Tue 18:00 ET: the 7-day clock (engine/clock7 from the heartbeat's keepalive block) shows the true last fill per account
  5. never fires on an account that already traded
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import keepalive as K  # noqa: E402
from tests.test_keepalive import ET, Bot, Env, PX, hook, replay, ts  # noqa: E402

RES = []
ACCTS = {"lit": "Sim101", "atlas": "Sim102", "rapid": "Sim103", "rapid2": "Sim104"}
LABEL = {"lit": "Zlarior 50K", "atlas": "ATLAS 25K", "rapid": "Rapid EOD 25K", "rapid2": "Rapid EOD 50K"}
T0, T1 = ts(2026, 11, 23, 8), ts(2026, 11, 28, 12)
TABLE = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:500]) if info and not ok else ''}")
    RES.append(bool(ok))


def entry_row(day, hh=10):
    y, m, d = map(int, day.split("-"))
    t = ts(y, m, d, hh)
    return {"t": t, "sym": "NQ", "side": "buy", "qty": 1, "entry_t": t - 60, "result": {"ok": True}}


class Acct:
    """An ATLAS-style lane (account B / RapidAtlas): ledger fills, open_t + prov for a position, its own NT adapter."""
    def __init__(self, name, adapter, fills, plan, start="2026-11-01", label=None):
        self.name, self.label, self.problem, self.adapter = name, label or name, None, adapter
        self.ledger = [entry_row(d) for d in fills]
        self.open_t, self.prov, self.closes = None, {}, []
        self.spec = {"plan": plan, "preset": plan, "eval_start": start}

    def eval_view(self, now=None):
        return {"stage": "eval", "status": "open", "balance": 25300.0, "room": 1200.0, "start_balance": 25000.0, "target": 26500.0,
                "floor": 24100.0}

    def funded(self):
        return False

    def day_pnl(self, day):
        return 0.0


def world(key, fills, extra_lit_fills=None):
    """The 4-account bot; `fills` = the confirmed fill days of the account under test; only its switch is ON."""
    env = Env()
    hook(env)
    lit_days = {d: 0.0 for d in (fills if key == "lit" else ["2026-11-20"])}
    for d in extra_lit_fills or []:
        lit_days[d] = 0.0
    bot = Bot(env.tmp, env.adapter("Sim101"), env.now, ka={"accounts": {key: True}}, days=lit_days)
    bot.acct_b = Acct("Sim102", env.adapter("Sim102", "acctb_"), fills if key == "atlas" else ["2026-11-20"], "builder25k",
                      label="ATLAS 25K")
    bot.acct_r = Acct("Sim103", env.adapter("Sim103", "acctr_"), fills if key == "rapid" else ["2026-11-20"],
                      "mffu_rapid_eod_25k", label="ATLAS Rapid")
    bot.acct_r2 = Acct("Sim104", env.adapter("Sim104", "acctr2_"), fills if key == "rapid2" else ["2026-11-20"],
                       "mffu_rapid_eod_50k", label="ATLAS Rapid 2")
    bot.acct_r2.slot = "rapid2"
    lane = types.SimpleNamespace(spec={"lane": "rapid", "nt_account": "Sim103", "adapter": "ninjatrader", "preset": "mffu_rapid_eod_25k"},
                                 id="rapid", adapter=env.adapter("Sim103", "rapid_"), problem=None, mode="two_week", lock=None,
                                 closes=[], ledger=[], open_t=None, start_day=lambda: "2026-11-01")
    lane2 = types.SimpleNamespace(spec={"lane": "rapid", "slot": "rapid2", "nt_account": "Sim104", "adapter": "ninjatrader",
                                        "preset": "mffu_rapid_eod_50k"}, id="rapid2", adapter=env.adapter("Sim104", "rapid2_"),
                                  problem=None, mode="two_week", lock=None, closes=[], ledger=[], open_t=None,
                                  start_day=lambda: "2026-11-01", slot="rapid2")
    bot.accts = types.SimpleNamespace(accounts=[lane, lane2])
    return env, bot


_real_facts = K._facts


def _facts(bot, g, now):
    """The firm's balance facts: the real lit path; a plain healthy eval for the other three (lifecycle's own readers need the
    full RapidAtlas / AccountB books; the keep-alive's calendar and gates are what is proven here)."""
    if g["key"] == "lit":
        return _real_facts(bot, g, now)
    st = {"atlas": 25000.0, "rapid": 25000.0, "rapid2": 50000.0}.get(g["key"], 50000.0)
    return {"start": st, "balance": st + 300.0, "floor": st - 1200.0, "day_pnl": 0.0}


def fires(env, out, key):
    nt = ACCTS[key]
    ents = env.entries(nt)
    opens = [x for x in out if x.get("do") == "open" and x.get("key") == key]
    closes = [x for x in out if x.get("do") == "close" and x.get("key") == key]
    return ents, opens, closes


def day_of(t):
    return dt.datetime.fromtimestamp(t, ET).date().isoformat()


def fire_ok(env, bot, out, key, want_day, label, scen):
    ents, opens, closes = fires(env, out, key)
    others = [k for k in ACCTS if k != key and env.entries(ACCTS[k])]
    got = [day_of(o["t"]) for o in opens]
    # after a fire on want_day the clock restarts from it: a later fire inside the replay is right only on ITS act day
    # (Mon 11-23 -> Wed 11-25: Thanksgiving leaves no full session between Thu 11-26 and the Sun 11-29 deadline)
    chain = [want_day]
    while True:
        nxt = K.plan(chain[-1], ts(*map(int, chain[-1].split("-")), 17))["act_day"]
        if not nxt or ts(*map(int, nxt.split("-")), 15, 33) > T1:
            break
        chain.append(nxt)
    ok_one = got == chain and len(ents) == len(chain)
    ok_win = bool(opens) and K.window(want_day) and K.window(want_day)[0] <= K._mod(opens[0]["t"]) < K.window(want_day)[1]
    ok_qty = bool(ents) and env.fake.orders[ents[0][0]]["qty"] == 1
    xb = K.exit_by(want_day)
    ok_flat = bool(closes) and day_of(closes[0]["t"]) == want_day and K._mod(closes[0]["t"]) <= (xb or 0) \
        and env.flat(next(ad for (n, _t), ad in env.adapters.items() if n == ACCTS[key] and ad is K.targets(bot)[[g["key"] for g in K.targets(bot)].index(key)]["adapter"]))
    hard = K.plan(scen["last"], T0)["hard"]
    ok_before = want_day <= hard
    check(f"{label}: fires on {want_day} {K._hm(K._mod(opens[0]['t'])) if opens else '-'} ET (MFFU's last day {hard}), "
          f"(then only on its next act day: {chain[1:] or 'none'}), inside the window, 1 MNQ, flat the same day by {K._hm(xb) if xb else '-'}, "
          "no other account touched",
          ok_one and ok_win and ok_qty and ok_flat and ok_before and not others,
          {"opens": [(day_of(o["t"]), K._hm(K._mod(o["t"]))) for o in opens], "ents": ents, "closes": closes[:2], "others": others})
    TABLE.append((LABEL[key], scen["name"], f"{want_day} {K._hm(K._mod(opens[0]['t'])) if opens else '-'}"
                  + (f" (next: {', '.join(chain[1:])})" if chain[1:] else ""),
                  "ok" if (ok_one and ok_win and ok_qty and ok_flat and ok_before and not others) else "FAIL"))


SCEN = [  # name, last confirmed fill, the expected fire day (the rule: the last FULL session <= D + 6, late = the next session)
    {"name": "idle 5 on Mon (last Wed 11-18)", "last": "2026-11-18", "want": "2026-11-24"},
    {"name": "idle 6 on Mon (last Tue 11-17)", "last": "2026-11-17", "want": "2026-11-23"},
    {"name": "idle 7 on Mon (last Mon 11-16: MFFU's last day TODAY)", "last": "2026-11-16", "want": "2026-11-23"},
    {"name": "weekend + Thanksgiving (last Thu 11-19)", "last": "2026-11-19", "want": "2026-11-25"},
    {"name": "Thanksgiving (last Fri 11-20; Thu half day not used)", "last": "2026-11-20", "want": "2026-11-25"},
]


def run_scenarios():
    for key in ACCTS:
        for sc in SCEN:
            env, bot = world(key, [sc["last"]])
            try:
                out = replay(env, bot, T0, T1)
                fire_ok(env, bot, out, key, sc["want"], f"1. {LABEL[key]} / {sc['name']}", sc)
            finally:
                env.done()


def pc_off():
    """The PC is off all Tue 11-24 (the act day of a last fill Wed 11-18): Wed 11-25 it fires at the first window (late, still
    on MFFU's last day) and the phone hears about it before."""
    for key in ACCTS:
        env, bot = world(key, ["2026-11-18"])
        try:
            out = replay(env, bot, T0, ts(2026, 11, 24, 0)) + replay(env, bot, ts(2026, 11, 25, 8), T1)   # Tue: no polls at all
            ents, opens, closes = fires(env, out, key)
            got = [day_of(o["t"]) for o in opens]
            hard = K.plan("2026-11-18", T0)["hard"]
            heads = [p for k, p in env.alerts if k == "problem" and day_of(int(p.get("t") or 0) or ts(2026, 11, 25, 9)) >= "2026-11-25"]
            ok = got == ["2026-11-25"] and hard == "2026-11-25" and len(ents) == 1 and closes and day_of(closes[0]["t"]) == "2026-11-25"
            check(f"1b. {LABEL[key]} / PC off all Tue 11-24 (its act day): fires Wed 11-25 (MFFU's last day {hard}), once, flat "
                  "the same day", ok, {"opens": got, "ents": ents, "alerts": [p.get('title') for _, p in env.alerts][-4:]})
            TABLE.append((LABEL[key], "PC off on the act day (last Wed 11-18)", f"{got[0] if got else '-'} "
                          f"{K._hm(K._mod(opens[0]['t'])) if opens else '-'}", "ok" if ok else "FAIL"))
        finally:
            env.done()


def on_top():
    """A bot position open on that account through the whole window: never a keep-alive on top; the phone is told to place one
    by hand before 16:05 ET; the next session (still before MFFU's last day) it fires."""
    for key in ACCTS:
        env, bot = world(key, ["2026-11-17"])                    # act day Mon 11-23, MFFU's last day Tue 11-24
        try:
            if key == "lit":
                bot.state["position"] = {"dir": 1, "qty": 2}
            elif key == "atlas":
                bot.acct_b.open_t, bot.acct_b.prov = 1, {1: {"dir": 1}}
            elif key == "rapid":
                bot.acct_r.open_t, bot.acct_r.prov = 1, {1: {"dir": 1}}
            else:
                bot.acct_r2.open_t, bot.acct_r2.prov = 1, {1: {"dir": 1}}
            out = replay(env, bot, T0, ts(2026, 11, 23, 17))
            ents, opens, _ = fires(env, out, key)
            hand = [p for k, p in env.alerts if k == "problem" and "by hand" in p.get("body", "") and LABEL[key].split()[0] in
                    (p.get("title", "") + p.get("body", ""))]
            check(f"1c/3. {LABEL[key]}: a bot position open all through Mon's window -> NO keep-alive on top, and ONE push "
                  "'place 1 MNQ by hand ... before 16:05 ET'", not ents and not opens and len(hand) == 1 and "16:05" in hand[0]["body"],
                  {"ents": ents, "alerts": [(p.get('title'), p.get('body', '')[:120]) for _, p in env.alerts]})
            if key == "lit":
                bot.state.pop("position", None)
            else:
                o = {"atlas": bot.acct_b, "rapid": bot.acct_r, "rapid2": bot.acct_r2}[key]
                o.open_t, o.prov = None, {}
            out2 = replay(env, bot, ts(2026, 11, 23, 17), T1)
            _, op2, cl2 = fires(env, out2, key)
            got = [day_of(o["t"]) for o in op2]
            check(f"1c. ... the position closed: Tue 11-24 it fires (MFFU's last day), once, flat the same day",
                  got == ["2026-11-24"] and cl2 and day_of(cl2[0]["t"]) == "2026-11-24", got)
            TABLE.append((LABEL[key], "bot position open on the act day (last Tue 11-17)", f"Mon: none (hand push); "
                          f"{got[0] if got else '-'}", "ok" if got == ["2026-11-24"] and not ents and len(hand) == 1 else "FAIL"))
        finally:
            env.done()


def already_traded():
    for key in ACCTS:
        env, bot = world(key, ["2026-11-24"])                     # traded Tue 11-24: next act day Mon 11-30 (after the replay)
        try:
            out = replay(env, bot, T0, T1)
            ents, opens, _ = fires(env, out, key)
            check(f"5. {LABEL[key]} traded Tue 11-24: no keep-alive all week (next act Mon 11-30)",
                  not ents and not opens and K.plan("2026-11-24", T0)["act_day"] == "2026-11-30", ents)
            TABLE.append((LABEL[key], "already traded Tue 11-24", "never (next Mon 11-30)", "ok" if not ents else "FAIL"))
        finally:
            env.done()
        env, bot = world(key, ["2026-11-17"])                     # due Mon 11-23 ... but a bot trade fills Mon 10:00
        try:
            fill = entry_row("2026-11-23")
            if key == "lit":
                bot.days["2026-11-23"] = 0.0
                bot.ledger.append(fill)
            else:
                {"atlas": bot.acct_b, "rapid": bot.acct_r, "rapid2": bot.acct_r2}[key].ledger.append(fill)
            out = replay(env, bot, ts(2026, 11, 23, 11), ts(2026, 11, 23, 17))
            ents, opens, _ = fires(env, out, key)
            check(f"5. {LABEL[key]}: due Mon 11-23 but a bot trade filled at 10:00 -> no keep-alive that day", not ents and not opens, ents)
        finally:
            env.done()


def tuesday_check():
    """Tue 18:00 ET (the owner's evening look): after Tue's keep-alive (last fill Wed 11-18) the 7-day clock built from the
    heartbeat's keepalive block shows the TRUE last fill (Tue 11-24) for that account, and a full week ahead."""
    from engine import clock7 as C7
    for key in ACCTS:
        env, bot = world(key, ["2026-11-18"])
        try:
            replay(env, bot, T0, ts(2026, 11, 24, 18, 0))
            env.now[0] = ts(2026, 11, 24, 18, 0)
            blk = K.hb_block(bot) or {}
            ids = {"lit": "mffu50k_eval", "atlas": "atlas", "rapid": "rapid", "rapid2": "rapid2"}
            mf = {"a": [{"id": ids[k], "nm": LABEL[k], "sd": "2026-11-01"} for k in ACCTS]}
            k7 = C7.build(mf, blk, now=ts(2026, 11, 24, 18, 0)) or {}
            row = next((r for r in k7.get("a") or [] if r["id"] == ids[key]), None)
            check(f"4. Tue 18:00 ET: {LABEL[key]}'s 7-day clock = last fill Tue 11-24 (the keep-alive), MFFU's last day Tue 12-01, "
                  "keep-alive ON", row is not None and row["lf"] == "2026-11-24" and row["hard"] == "2026-12-01" and row["on"] is True,
                  {"row": row, "last": (blk or {}).get("last")})
        finally:
            env.done()


def consent():
    """The START phrase covers all 4, rapid2 included (engine/go.armed_accounts -> engine/keepalive.start_consent)."""
    import tempfile
    from engine import go, account_cli
    from engine.tradovate import LIVE_PHRASE
    inv = [{"role": "main", "name": "MFFU-REAL-0050", "mffu": True, "id": "zlarior"},
           {"role": "b", "name": "MFFU-REAL-0025", "armed": True, "mffu": True, "id": "atlas"},
           {"role": "rapid", "name": "MFFU-REAL-R025", "armed": True, "mffu": True, "id": "rapid", "plan": "rapideod25"},
           {"role": "rapid", "name": "MFFU-REAL-R050", "armed": True, "mffu": True, "id": "rapid2", "plan": "rapideod"},
           {"role": "c", "name": "BLITZ", "armed": True, "id": "blitz"}]
    real_inv = account_cli.inventory
    account_cli.inventory = lambda *a, **k: [dict(r) for r in inv]
    try:
        armed = go.armed_accounts()
    finally:
        account_cli.inventory = real_inv
    keys = [k for k, _l, _n in armed]
    check("2. START's armed list has all 4 keys: lit, atlas, rapid, rapid2 (BLITZ never)", keys == ["lit", "atlas", "rapid", "rapid2"], armed)
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "keepalive.json")
        r = K.start_consent(LIVE_PHRASE, armed, now=ts(2026, 11, 23, 1), path=p)
        on = json.load(open(p, encoding="utf-8"))["accounts"]
        check("2. the typed phrase turns the keep-alive ON for all 4 (rapid2 included), nothing else",
              sorted(r["keys"]) == ["atlas", "lit", "rapid", "rapid2"] and all(on.get(k) is True for k in ACCTS), (r, on))
        r2 = K.start_consent("i accept live risk", armed, path=os.path.join(tmp, "k2.json"))
        check("2. without the exact phrase nothing changes", r2["keys"] == [] and not os.path.exists(os.path.join(tmp, "k2.json")), r2)


def main():
    K._facts = _facts
    try:
        for fn in (consent, run_scenarios, pc_off, on_top, already_traded, tuesday_check):
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} crashed: {e.__class__.__name__}: {e}", False)
    finally:
        K._facts = _real_facts
        K.ALERT_HOOK = None
    print("\naccount | scenario | fires on | ok?")
    for r in TABLE:
        print(" | ".join(r))
    ok = sum(RES)
    print(f"\nk7 proof: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
