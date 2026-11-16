"""Account B: the second strategies on their OWN prop account next to LIT's (engine/account_b.py). Sim / fake NinjaTrader
only (engine/ninjatrader._FakeNT on a temp folder: LIT on Sim101, account B on Sim102); nothing is ever armed for a real
account and second_model.json is never edited by this test (the start cfg "account_b" switches B on for the harness).

    python -X utf8 -m tests.test_second_account_b            # everything (~85 min on 4 cores)
    python -X utf8 -m tests.test_second_account_b --quick    # unit checks + one day + crash (~25 min)

 a. off = today: second_model.json ships "account_b": null; tests.test_lit_live --days --bot (120/120, LiveBot 2/2/2/2);
    a LiveBot day with B off: no account B object, no B order file, LIT's orders as run lit_live.
 b. on (fake Sim102, Builder 25K and 50K): 2026 days where B trades while LIT trades on Sim101: every B trade of the
    research (EMA / MACD / S/R) routed to Sim102 at its 5m open with the plan's size (engine/account_b.qty on B's own
    eval state), its stop / target / exit; LIT's trades unchanged; both positions at once in the same direction allowed;
    never long on one account and short on the other at any poll (fake NinjaTrader positions); one position and max 2
    entries a day on B.
 c. the no-opposite rule: a B entry is blocked while LIT holds / enters / has an armed setup the other way; LIT entering
    the other way while B is open closes B at market BEFORE LIT's order (HEDGE); unit checks on lit_opposite / lit_entering.
 d. B's eval: sizing per plan (25K: 20 micros, 50% room, $600 soft loss; 50K: 40, 60%, $1,000), pass lock (no trade, one
    push), fail / stuck lock, the soft daily loss lock-out, sessions from eval_start; the switch (refused when the self-test
    fails, the one line changed, off restores the file byte for byte, B's strategies never routed on LIT's account).
 e. a crash in B never touches LIT (LIT's orders and delays identical to B off).
 f. restart mid-trade on B: a new LiveBot on the same state finds B's open position and manages it to its exit; LIT's
    reconcile guard never flattens anything.
Results -> research/second/account_b_check.json.
"""
from __future__ import annotations

import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import account_b as AB  # noqa: E402
from engine import live  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402
from engine import second  # noqa: E402
from engine.live import tick_px  # noqa: E402
from tests import test_second_route as TR  # noqa: E402
from tests.test_second_route import Harness, Ref, at, hm, kind_reason  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "account_b_check.json")
RESULTS = TR.RESULTS
check = TR.check
KEYS = ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]


def ab_block(plan, day, sizing="need", prior=0.0):
    return {"account": "Sim102", "plan": plan, "eval_start": day, "strategies": list(KEYS), "sizing": sizing, "prior_pnl": prior}


def install_factory(H):
    """Account B's NinjaTrader adapter on the harness clock + the same fake NinjaTrader folder (Sim102)."""
    def fac(spec, cfg):
        if cfg["adapter"] != "ninjatrader":
            return live.ADAPTERS[cfg["adapter"]](cfg)
        ad = nt.NinjaTraderAdapter(cfg, clock=H.clock)
        ad._alert_fn = lambda *a, **k: None
        clock = H.clock

        def sl(s_):
            if H._fake is not None:
                H._fake.process()
            clock.base += s_
        ad._sleep = sl
        return ad
    AB.ADAPTER_FACTORY = fac


def bot_b(H, tag, start_t, ab, fake=None):
    H._fake = None
    folder = os.path.join(H.tmp, tag, "NinjaTrader 8")
    fake = fake or nt._FakeNT(folder, price=25000.0)
    H._fake = fake
    b, fake = H.bot(tag, [], start_t, fake=fake, cfg_extra={"account_b": ab})
    return b, fake


def run(H, b, fake, wakes, errors, on_poll=None):
    """Harness.run + the B adapter's processing; records both accounts' positions at every poll."""
    seen = []

    def poll(bot, w):
        p1 = sum(q for (a, _), (q, _x) in fake.pos.items() if a == "Sim101")
        p2 = sum(q for (a, _), (q, _x) in fake.pos.items() if a == "Sim102")
        seen.append((int(w), p1, p2))
        if on_poll:
            on_poll(bot, w)
    H.run(b, fake, wakes, errors, on_poll=poll)
    return seen


def poll_times(H, day):
    return H.times(day, KEYS)


def research_b(H, day):
    return sorted([dict(t, key=k) for k in KEYS for t in H.ref.sec[k].get(day, [])], key=lambda t: (int(t["entry_t"]), KEYS.index(t["key"])))


def b_day(H, day, plan, label, sizing="need", prior=0.0, expect_hedge=False, expect_same=False):
    """One session with LIT on Sim101 and account B on Sim102: checks every research trade of B and LIT."""
    ab = ab_block(plan, day, sizing, prior)
    b, fake = bot_b(H, f"{plan}_{day}", at(day, 1, 45), ab)
    B = b.acct_b
    check(f"{label}: account B started on Sim102 ({AB.PLANS[plan]['label']}), no problem", B is not None and not B.disabled_reason(),
          B and B.disabled_reason())
    errors = []
    t0 = time.time()
    pos = run(H, b, fake, poll_times(H, day), errors)
    L = H.ref.lit.get(day, [])
    led = b.ledger
    ent = {r["entry_t"]: r for r in led if r.get("side") in ("buy", "sell")}
    exi = {r["entry_t"]: r for r in led if r.get("side") == "exit" and r.get("entry_t")}
    lit_ok = all(int(t["entry_t"]) in ent and ent[int(t["entry_t"])]["side"] == ("buy" if t["dir"] == 1 else "sell")
                 and int(t["entry_t"]) in exi and exi[int(t["entry_t"])]["reason"] == kind_reason(t["exit"]) for t in L)
    check(f"{label}: LIT's {len(L)} trade(s) routed on Sim101 and exited as run lit_live", lit_ok and not any(r.get("src") for r in led),
          [(hm(t["entry_t"]), t["exit"], ent.get(int(t["entry_t"])), exi.get(int(t["entry_t"]))) for t in L])
    bent = {r["entry_t"]: r for r in B.ledger if r.get("side") in ("buy", "sell")}
    bexi = {r["entry_t"]: r for r in B.ledger if r.get("side") == "exit" and r.get("entry_t")}
    bmods = collections.defaultdict(list)
    for r in B.ledger:
        if r.get("side") == "modify":
            bmods[r["entry_t"]].append(r)
    rows, open_until, n_today = [], 0, 0
    logs = [x["text"] for x in b.log]
    for u in research_b(H, day):
        et_, d = int(u["entry_t"]), int(u["dir"])
        e = bent.get(et_)
        if et_ < open_until or n_today >= AB.MAX_PER_DAY:
            check(f"{label}: B {u['key']} {hm(et_)} not routed (account B already in a trade / 2 a day)", e is None
                  or e.get("src") != u["key"], e)
            rows.append({"entry": hm(et_), "key": u["key"], "routed": False, "why": "B busy"})
            continue
        lit_opp = next((t for t in L if int(t["dir"]) == -d and int(t["entry_t"]) <= et_ < int(t["exit_t"])), None)
        blocked = [x for x in logs if "NOT routed on account B" in x and f"{hm(et_)[:5]} ET open" in x]
        if lit_opp is not None:
            check(f"{label}: B {u['key']} {hm(et_)} {'LONG' if d == 1 else 'SHORT'} blocked: LIT's {'SHORT' if d == 1 else 'LONG'} "
                  f"trade from {hm(lit_opp['entry_t'])} is open (no hedging)", e is None and any("no hedging" in x for x in blocked), blocked)
            rows.append({"entry": hm(et_), "key": u["key"], "routed": False, "why": "LIT opposite open"})
            continue
        if e is None:
            ok = any("no hedging: LIT has a" in x or "no hedging: LIT is entering" in x for x in blocked)
            check(f"{label}: B {u['key']} {hm(et_)} not routed: LIT armed / entering the other way (stricter than the research)",
                  ok, blocked or [x for x in logs if "account B" in x][-5:])
            rows.append({"entry": hm(et_), "key": u["key"], "routed": False, "why": "LIT armed opposite"})
            continue
        # expected size from B's own eval state at that moment (its closes before this entry)
        closes = [(dd, t_, p) for dd, t_, p, *rest in B.closes if int(t_) <= int(e["t"])]
        st = MA.sizing_state("two_week", closes, live.trading_day(et_), day, B.rules, prior=prior, n_today=n_today)
        q_want = AB.qty(B.spec, {"risk_pts": abs(float(u["entry"]) - float(u["stop"])), "tgt_pts": abs(float(u["target"]) - float(u["entry"]))},
                        st, base=b._lit_sizing)["qty"]
        delay = round(float(e["t"]) - et_, 2)
        okE = e.get("src") == u["key"] and e["side"] == ("buy" if d == 1 else "sell") and int(e["qty"]) == int(q_want) \
            and abs(float(e["stop"]) - tick_px(u["stop"], d)) < 1e-6 and abs(float(e["target"]) - tick_px(u["target"], d, target=True)) < 1e-6
        check(f"{label}: B {u['key']} {hm(et_)} routed on Sim102 like the research trade ({q_want} micros on B's eval, stop, target) "
              f"{delay} s after its 5m open", okE and delay <= 10.0, ({k: e.get(k) for k in ("t", "side", "qty", "stop", "target", "src")}, u, q_want))
        n_today += 1
        x = bexi.get(et_)
        pre = next((t for t in L if int(t["dir"]) == -d and et_ < int(t["entry_t"]) < int(u["exit_t"])), None)
        if pre is not None:
            le = ent.get(int(pre["entry_t"]))
            okX = x is not None and x["reason"] == "HEDGE" and le is not None and float(x["t"]) <= float(le["t"])
            check(f"{label}: B {u['key']} {hm(et_)} closed at market (HEDGE) when LIT entered the other way at {hm(pre['entry_t'])}, "
                  "before LIT's order", okX, (x, le))
            open_until = int(x["t"]) if x else int(u["exit_t"])
        else:
            want = kind_reason(u["exit_kind"])
            usd = float(u.get("pnl_usd") if u.get("pnl_usd") is not None else u.get("pnl"))
            pnl_want = round(usd * int(q_want) / int(u["qty"]), 2)
            got = next((c[2] for c in B.closes if len(c) > 3 and int(c[3]) == et_), None)
            okX = x is not None and x["reason"] == want and got is not None and abs(float(got) - pnl_want) <= max(0.05, 0.03 * int(q_want))
            check(f"{label}: B {u['key']} {hm(et_)} exit {want} with the research $ ({pnl_want:+,.2f}) booked on B's eval", okX,
                  (x and {k: x.get(k) for k in ("t", "reason", "pnl", "pnl_est")}, got, u.get("exit_kind")))
            if want == "BE":
                be = tick_px(float(u["entry"]) + d * 1.25, d)
                check(f"{label}: B {u['key']} {hm(et_)} breakeven move routed on Sim102 (stop -> {be:,.2f})",
                      any(abs(float(m["stop"]) - be) < 1e-6 and (m.get("result") or {}).get("ok") for m in bmods.get(et_, [])), bmods.get(et_))
            open_until = int(u["exit_t"])
        rows.append({"entry": hm(et_), "key": u["key"], "routed": True, "qty": e.get("qty"), "exit": x and x.get("reason"),
                     "pnl": next((c[2] for c in B.closes if len(c) > 3 and int(c[3]) == et_), None)})
    opp = [(hm(w), p1, p2) for w, p1, p2 in pos if p1 * p2 < 0]
    both = [(hm(w), p1, p2) for w, p1, p2 in pos if p1 * p2 > 0]
    check(f"{label}: never long on one account and short on the other at any poll ({len(pos)} polls)", not opp, opp[:5])
    if expect_same:
        check(f"{label}: both accounts in a position at once in the same direction (allowed: {len(both)} polls)", bool(both), both[:3])
    if expect_hedge:
        check(f"{label}: a HEDGE close happened on account B", any(r.get("reason") == "HEDGE" for r in B.ledger), B.ledger[-4:])
    bn = collections.Counter(live.trading_day(int(r["entry_t"])) for r in B.ledger if r.get("side") in ("buy", "sell"))
    check(f"{label}: account B <= 2 entries a day, one position (fake Sim102 never above one entry's size)",
          max(bn.values() or [0]) <= AB.MAX_PER_DAY and max((abs(p2) for _, _, p2 in pos), default=0) <= max((int(r["qty"]) for r in bent.values()), default=0)
          , (bn, max((abs(p2) for _, _, p2 in pos), default=0)))
    recon = [r for r in led + B.ledger if r.get("reason") == "RECONCILE"]
    check(f"{label}: no error, no RECONCILE flatten, no DESYNC, no account B error", not errors and not recon and not b.health.get("desync")
          and not [x for x in logs if "account B failed" in x], (errors[:3], recon[:2], [x for x in logs if "account B failed" in x][:2]))
    # trade watch (night W1 2026-11-16): every research signal B saw and did not route carries B's own reason ("held"), and the
    # ATLAS twin of tools/trade_watch.py (engine/second.run on the same bars) finds no mismatch on a day traded like the research
    held_hm = {hm(int(k)) for k in B.held}
    nb = [r["entry"] for r in rows if not r["routed"] and r["why"] != "B busy"]
    check(f"{label}: trade watch: each blocked B signal has its reason in B's state ({len(nb)})", all(x in held_hm for x in nb),
          (nb, sorted(held_hm)))
    from tools import trade_watch as TW
    wr = tempfile.mkdtemp(prefix="le_tw_")
    try:
        os.makedirs(os.path.join(wr, "data"))
        with open(os.path.join(wr, "data", "live_state_acctb.json"), "w", encoding="utf-8") as fh:
            json.dump(B.blob(), fh, default=str)
        with open(os.path.join(wr, "data", "account_b.json"), "w", encoding="utf-8") as fh:
            json.dump({"account_b": {"account": B.name, "strategies": list(B.spec["keys"])}}, fh)
        fl = TW.atlas_flags(wr, at(day, 16, 10))
    finally:
        shutil.rmtree(wr, ignore_errors=True)
    # the fake Sim102 fills at the bot's mark (the last close), not at the 5m open the research fills at, so a "slip" here is
    # the harness's fill model; a missed entry or a stop off the twin would be a real live != backtest difference
    check(f"{label}: trade watch: the ATLAS twin finds no missed entry and no stop mismatch on B's day",
          not [f for f in fl if f["code"] != "slip"], fl)
    info = b.second_route_info() or {}
    abv = info.get("account_b") or {}
    check(f"{label}: heartbeat / dashboards show '{B.label}' with its eval tracker", abv.get("label") == "ATLAS Sim102"
          and (abv.get("eval") or {}).get("target") == B.rules["start"] + B.rules["target"], abv.get("eval"))
    cp = second.compact({"t": 1, "day": day, "strategies": {k: {"label": k, "short": k, "on": True, "trades": []} for k in KEYS}}, route=info)
    check(f"{label}: second.compact labels B's strategies 'ROUTED on ATLAS Sim102'",
          all((cp["strategies"][k]["route_label"] == "ROUTED on ATLAS Sim102") for k in KEYS) and cp["route"].get("account_b"), cp.get("route"))
    return {"day": day, "plan": plan, "rows": rows, "lit": len(L), "seconds": round(time.time() - t0), "bot": b}


# ------------------------------------------------------------------------------------------------ units
class FakeBot:
    def __init__(self, now, state=None, ledger=None, open_routed=None):
        self._now = now
        self.state = state or {}
        self.ledger = ledger or []
        self._open_routed = open_routed
        self.accts = None
        self.cfg = {"adapter": "paper", "sym": "NQ"}
        self.health = {}
        self.kill = False
        self.state_path = None
        self.logs = []
        self.pushed = []

    def clock(self):
        return self._now

    def _log(self, kind, text, **kw):
        self.logs.append((kind, text))

    def _note_error(self, text):
        self.logs.append(("error", text))

    def _push_send(self, p):
        self.pushed.append(p)


def units(tmp):
    print("unit checks: config, sizing per plan, eval lock, no-opposite, switch", flush=True)
    shipped = json.load(open(second.CFG_PATH, encoding="utf-8"))
    check("second_model.json ships \"account_b\": null (account B off)", "account_b" in shipped and shipped["account_b"] is None
          and AB.raw_cfg() is None and AB.keys_on_b() == [])
    # config problems
    sc = second.load_cfg()
    p = lambda ab, lit=None: (AB.normalize(ab, sc, lit) or {}).get("problem")
    check("config: B on LIT's own account refused", "LIT's own account" in (p({"account": "Sim101", "plan": "builder25k"}, "Sim101") or ""))
    check("config: unknown plan / sizing / strategy / cloud-only refused",
          p({"account": "Sim102", "plan": "pro150k"}) and p({"account": "Sim102", "plan": "builder25k", "sizing": "max"})
          and p({"account": "Sim102", "plan": "builder25k", "strategies": ["nope"]}) and p({"account": "Sim102", "plan": "builder25k", "strategies": ["lit_asia"]}))
    check("config: a valid block has no problem", p(ab_block("builder25k", "2026-10-01")) is None and p(ab_block("builder50k", "2026-10-01")) is None)
    # sizing per plan
    s25 = AB.normalize(ab_block("builder25k", "2026-10-01"), sc)
    s50 = AB.normalize(ab_block("builder50k", "2026-10-01"), sc)
    st = lambda room, prof=0.0, cum=0.0, sess=1: {"profit": prof, "cum": cum, "room": room, "session": sess, "n_today": 0, "days_traded": 0}
    q25 = AB.qty(s25, {"risk_pts": 10.0, "tgt_pts": 15.0}, st(1000.0))
    q50 = AB.qty(s50, {"risk_pts": 10.0, "tgt_pts": 15.0}, st(2000.0))
    check(f"sizing 25K need: one winner passes capped at 50% of the $1,000 room and 20 micros -> {q25['qty']}", q25["qty"] == 20, q25)
    check(f"sizing 50K need: capped at 40% of the $2,000 room (owner 'yes 40%' 2026-11-14), the $1,000 soft loss, 40 micros -> {q50['qty']}", q50["qty"] == 35, q50)
    a, b_ = AB.qty(s25, {"risk_pts": 30.0, "tgt_pts": 60.0}, st(1000.0)), AB.qty(s50, {"risk_pts": 30.0, "tgt_pts": 60.0}, st(2000.0))
    check(f"sizing 30-pt stop: 25K {a['qty']} (50% x $1,000 / $60 = 8) vs 50K {b_['qty']} (min(26 need, 40% room 12, 15 dll))",
          a["qty"] == 8 and b_["qty"] == 12, (a, b_))
    d25 = AB.qty(s25, {"risk_pts": 20.0, "tgt_pts": 40.0}, st(900.0, cum=-500.0))
    check(f"sizing 25K: the $600 soft daily loss (today -$500: $100 left) -> {d25['qty']}", d25["qty"] == 2, d25)
    # soft daily loss on EVERY trade (2026-10-22 fix, engine/account_b.dll_guard): after session 10 (safe_eval) and on the
    # 50K (no preset day guard) one full stop-out (stop + 2 ticks, $1.90 a micro) could exceed what is left of the day
    g50 = AB.qty(s50, {"risk_pts": 10.0, "tgt_pts": 15.0}, st(4000.0, cum=-200.0, sess=11))
    check(f"sizing 50K session 11: -$200 today, $800 left / $22.90 a micro full stop-out -> {g50['qty']} (was 40 = $916)",
          g50["qty"] == 34, g50)
    worst = []
    for spec in (s25, s50, {**s25, "sizing": "safe"}, {**s50, "sizing": "safe"}):
        dll = spec["rules"]["dll"]
        for sess in (1, 5, 10, 11, 15, 25):
            for room in (150.0, 400.0, 900.0, 1600.0, 3000.0, 5000.0):
                for cum in (-550.0, -300.0, 0.0, 250.0):
                    for rk in (6.0, 8.0, 10.0, 15.0, 25.0, 40.0, 80.0):
                        q_ = AB.qty(spec, {"risk_pts": rk, "tgt_pts": 2 * rk}, st(room, cum=cum, sess=sess))["qty"]
                        if q_ * ((rk + 0.5) * 2.0 + 1.90) > dll + cum + 1e-9:
                            worst.append((spec["plan"], spec.get("sizing"), sess, room, cum, rk, q_))
    check(f"sizing: one full stop-out never exceeds the rest of the soft daily loss (25K / 50K, need / safe, sessions 1-25; "
          f"{len(worst)} breaches)", not worst, worst[:5])
    sf = AB.qty({**s25, "sizing": "safe"}, {"risk_pts": 20.0, "tgt_pts": 40.0}, st(1000.0))
    check(f"sizing 25K safe: $150 / (20 x $2) = 3 -> {sf['qty']}", sf["qty"] == 3, sf)
    check("sizing: eval state unknown -> 0 (fails closed)", AB.qty(s25, {"risk_pts": 20.0, "tgt_pts": 40.0}, None)["qty"] == 0)
    for spec, tgt in ((s25, 1500.0), (s50, 3000.0)):
        r = AB.qty(spec, {"risk_pts": 20.0, "tgt_pts": 40.0}, {**st(1500.0, prof=tgt), "days_traded": 3})
        f = AB.qty(spec, {"risk_pts": 20.0, "tgt_pts": 40.0}, st(-5.0, prof=-1000.0))
        check(f"lock {spec['plan']}: passed (+${tgt:,.0f}) -> 0 micros; failed (room <= 0) -> 0", r["qty"] == 0 and f["qty"] == 0, (r, f))
    # eval tracker + lifecycle pushes on an AccountB with injected closes
    now = at("2026-10-07", 9, 0)
    fb = FakeBot(now)
    B = AB.AccountB(fb, AB.normalize(ab_block("builder25k", "2026-10-05"), sc), state_path=os.path.join(tmp, "b_state.json"))
    B.adapter = live.PaperAdapter({})
    B.closes = [["2026-10-05", now - 2 * 86400, 900.0, now - 2 * 86400 - 600], ["2026-10-06", now - 86400, 650.0, now - 86400 - 600]]
    ev = B.eval_view(now)
    check(f"eval 25K: balance ${ev['balance']:,.0f} >= target ${ev['target']:,.0f} -> passed, session {ev['session']}",
          ev["status"] == "passed" and ev["balance"] == 26550.0 and ev["target"] == 26500.0 and ev["session"] == 3, ev)
    B._lifecycle(now)
    B._lifecycle(now)
    check("eval: 'ATLAS Sim102 EVAL PASSED' pushed once", [p_["title"] for p_ in fb.pushed] == ["ATLAS Sim102 EVAL PASSED \U0001F389"],
          [p_["title"] for p_ in fb.pushed])
    B.closes = [["2026-10-05", now - 2 * 86400, -950.0, now - 2 * 86400 - 600]]
    ev = B.eval_view(now)
    check(f"eval 25K: -$950 -> room ${ev['room']:,.0f} < $100 -> stuck (no trade, push 'buy a new one')", ev["status"] == "stuck", ev)
    B.closes = [["2026-10-05", now - 2 * 86400, -1000.0, now - 2 * 86400 - 600]]
    check("eval 25K: -$1,000 -> failed", B.eval_view(now)["status"] == "failed")
    B.closes = [["2026-10-07", now - 600, -610.0, now - 1200]]
    B.check_lock(now)
    check("soft daily loss: -$610 on the 25K -> locked out for the day (LIT not affected)", B.lock and "soft daily loss" in B.lock["reason"], B.lock)
    s50b = AB.AccountB(fb, AB.normalize(ab_block("builder50k", "2026-10-05"), sc), state_path=os.path.join(tmp, "b50.json"))
    s50b.closes = [["2026-10-05", now - 2 * 86400, 1200.0, now - 2 * 86400 - 600]]
    e5 = s50b.eval_view(now)
    check(f"eval 50K: +$1,200 -> balance $51,200, floor ${e5['floor']:,.0f} (EOD trailing $2,000), target $53,000, open",
          e5["balance"] == 51200.0 and e5["floor"] == 49200.0 and e5["target"] == 53000.0 and e5["status"] == "open", e5)
    # no-opposite rule
    mk = lambda **kw: AB.AccountB(FakeBot(now, **kw), s25, state_path=os.path.join(tmp, "x.json"))
    check("no-opposite: LIT in a SHORT -> a B LONG blocked, a B SHORT allowed",
          mk(state={"position": {"dir": -1, "entry_t": now}}).lit_opposite(1) and mk(state={"position": {"dir": -1}}).lit_opposite(-1) is None)
    check("no-opposite: LIT entering SHORT -> B LONG blocked", "entering" in (mk(state={"enter_now": {"dir": -1}}).lit_opposite(1) or ""))
    check("no-opposite: LIT short setup armed (limit) -> B LONG blocked; long setup armed -> B LONG allowed",
          "armed" in (mk(state={"setups": {"short": {"dir": -1}}}).lit_opposite(1) or "") and mk(state={"setups": {"long": {}}}).lit_opposite(1) is None)
    check("no-opposite: LIT's routed SHORT on its account -> B LONG blocked",
          bool(mk(ledger=[{"side": "sell", "entry_t": now - 60}], open_routed=now - 60).lit_opposite(1)))
    Bh = mk()
    Bh.adapter = live.PaperAdapter({})
    Bh.prov = {now - 300: {"key": "ema_lon_vix", "short": "EMA", "dir": 1, "qty": 3, "entry": 25000.0, "day": "2026-10-07"}}
    Bh.open_t = now - 300
    Bh.lit_entering({"dir": 1, "entry_t": now, "entry": 25010.0}, "NQ", now)
    same_ok = Bh.open_t is not None
    Bh.lit_entering({"dir": -1, "entry_t": now, "entry": 25010.0}, "NQ", now)
    x = [r for r in Bh.ledger if r.get("side") == "exit"]
    check("lit_entering: LIT same direction -> B kept; LIT opposite -> B closed at market (HEDGE, $ booked at LIT's price)",
          same_ok and Bh.open_t is None and len(x) == 1 and x[0]["reason"] == "HEDGE" and abs(x[0]["pnl"] - 3 * ((25010 - 0.25 - 25000) * 2 - 1.9)) < 0.01, x)
    # startup reconcile on account B (bug hunt 2026-10-25: B routed before its own NinjaTrader account reconciled)
    class _StubNT:
        def __init__(self):
            self.probs = ["NinjaTrader shows LONG 2 MNQ 12-26 on Sim102 that no bracket of the bot explains"]

        def startup_problems(self):
            return list(self.probs)
    Bs = mk()
    Bs.bot.cfg = {"adapter": "ninjatrader", "sym": "NQ"}
    Bs.adapter = _StubNT()
    w1 = Bs.startup_block(now)
    Bs.adapter.probs = []
    w2 = Bs.startup_block(now + 60)
    Bs.adapter.probs = ["chart on MNQ 09-26"]
    w3 = Bs.startup_block(now + 120)
    check("startup: account B DISARMED while its own NinjaTrader account does not reconcile, then latched once it does",
          w1 and "STARTUP DISARMED" in w1 and "no bracket" in w1 and w2 is None and w3 is None and Bs._startup_ok == now + 60
          and any("STARTUP RECONCILED" in t for _, t in Bs.bot.logs), (w1, w2, w3))
    Bs2 = mk()
    Bs2.bot.cfg = {"adapter": "ninjatrader", "sym": "NQ"}

    class _Boom:
        def startup_problems(self):
            raise RuntimeError("bad file")
    Bs2.adapter = _Boom()
    Bp = mk()
    Bp.adapter = _StubNT()
    check("startup: a failing check keeps account B disarmed (fails closed); a paper bot has no gate",
          "STARTUP DISARMED" in (Bs2.startup_block(now) or "") and Bp.startup_block(now) is None)
    check("startup: the entry path asks startup_block before routing",
          "why_bar = self.startup_block(now)" in open(os.path.join(ROOT, "engine", "account_b.py"), encoding="utf-8").read())
    # the switch
    p_ = os.path.join(tmp, "second_model.json")
    shutil.copy(second.CFG_PATH, p_)
    raw = open(p_, encoding="utf-8").read()
    r1 = AB.set_account_b("Sim102", "builder25k", "2026-10-26", path=p_, selftest=lambda: (False, "FAIL (1/69)"))
    same = open(p_, encoding="utf-8").read() == raw and not os.path.exists(AB.local_path(p_))
    r0 = AB.set_account_b("Sim101x;", "builder25k", "2026-10-26", path=p_, selftest=lambda: (True, "PASS"))
    # route one strategy on LIT's account first: switching B on turns it off there
    second.set_route("ema_lon_vix", True, path=p_, selftest=lambda: (True, "PASS"))
    r2 = AB.set_account_b("Sim102", "builder25k", "2026-10-26", path=p_, selftest=lambda: (True, "PASS"))
    c2 = json.load(open(p_, encoding="utf-8"))
    b2, s2 = AB.raw_cfg(p_) or {}, second.load_cfg(p_).get("account_b") or {}
    r3 = second.set_route("macd_sweep", True, path=p_, selftest=lambda: (True, "PASS"))
    lines = [ln for a_, ln in zip(raw.splitlines(), open(p_, encoding="utf-8").read().splitlines()) if a_ != ln]
    r4 = AB.set_account_b("off", path=p_)
    back = open(p_, encoding="utf-8").read() == raw
    check("switch: refused when engine.ninjatrader --selftest fails (nothing written), refused for an invalid name", not r1["ok"] and same and not r0["ok"], (r1, r0))
    check("switch: --account-b Sim102 --plan builder25k --start writes the LOCAL data/account_b.json (second_model.json keeps "
          "account_b null, so it never blocks an update); B's strategies route off on LIT's account",
          r2["ok"] and b2.get("account") == "Sim102" and b2.get("plan") == "builder25k" and s2 == b2 and c2["account_b"] is None
          and r2["routed_off"] == ["ema_lon_vix"] and not any(c2["strategies"][k]["route"] for k in KEYS), (r2, lines[:3]))
    check("switch: a strategy on account B can not be routed on LIT's account too (--route refused)", not r3["ok"] and "account B" in r3["error"], r3)
    check("switch: --account-b off: the local file says off, second_model.json byte for byte as shipped", r4["ok"] and back
          and AB.read_local(p_) == (True, None) and AB.raw_cfg(p_) is None, r4)
    src = open(os.path.join(ROOT, "engine", "account_b.py"), encoding="utf-8").read()
    check("engine/account_b.py never arms anything (sets no environment switch, holds no LIVE phrase)",
          "os.environ[" not in src and "LIVE_PHRASE" not in src and "putenv" not in src)


# ------------------------------------------------------------------------------------------------ a. off
def part_a(H, quick=False):
    print("a. account B off = today", flush=True)
    if not quick:
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", "tests.test_lit_live", "--days", "--bot"], cwd=ROOT, capture_output=True,
                           text=True, timeout=2400)
        out = p.stdout or ""
        check("tests.test_lit_live --days --bot passes (120/120 day-end, LiveBot entries 2/2 exits 2/2)", p.returncode == 0, out[-1500:])
        print("     " + "\n     ".join([x for x in out.splitlines() if x.strip()][-4:]), flush=True)
    day = "2026-10-02"
    b, fake = bot_b(H, "off_" + day, at(day, 1, 45), None)
    errors = []
    run(H, b, fake, poll_times(H, day), errors)
    H._off_ref = b
    tagged = [f for f, _ in fake.files if "acctb" in f.lower()]
    lit = [r for r in b.ledger if r.get("side") in ("buy", "sell")]
    check(f"a. {day} B off: no account B (acct_b None, no acctb order file, no Sim102 position), LIT routed ({len(lit)})",
          b.acct_b is None and not tagged and not any(a == "Sim102" for a, _ in fake.pos) and len(lit) == len(H.ref.lit.get(day, []))
          and b.second_route_info() is None and not errors, (tagged[:2], errors[:2]))


# ------------------------------------------------------------------------------------------------ e. crash
def part_e(H):
    print("e. a crash in account B never touches LIT", flush=True)
    day = "2026-10-02"
    real = AB.AccountB.manage
    AB.AccountB.manage = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected account B failure"))
    real_e = AB.AccountB.entry
    AB.AccountB.entry = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected account B failure"))
    try:
        b, fake = bot_b(H, "exc_" + day, at(day, 1, 45), ab_block("builder25k", day))
        errors = []
        run(H, b, fake, poll_times(H, day), errors)
    finally:
        AB.AccountB.manage, AB.AccountB.entry = real, real_e
    real_t = AB.AccountB.tick
    AB.AccountB.tick = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected account B tick failure"))
    try:
        b3, fake3 = bot_b(H, "exc3_" + day, at(day, 1, 45), ab_block("builder25k", day))
        e3 = []
        run(H, b3, fake3, poll_times(H, day), e3)
    finally:
        AB.AccountB.tick = real_t
    b2 = getattr(H, "_off_ref", None)            # part a's B-off run of the same day = the reference
    if b2 is None:
        b2, fake2 = bot_b(H, "exc_ref_" + day, at(day, 1, 45), None)
        run(H, b2, fake2, poll_times(H, day), [])
    sig = lambda bb: [(r["entry_t"], r["side"], r.get("qty"), r.get("stop"), r.get("target"), r.get("reason")) for r in bb.ledger
                      if r.get("side") in ("buy", "sell", "exit", "modify")]
    dl = lambda bb: [round(r["t"] - r["entry_t"], 1) for r in bb.ledger if r.get("side") in ("buy", "sell")]
    err = [x["text"] for x in b.log if "account B failed" in x["text"]]
    err3 = [x for x in (b3.health.get("errors") or [])] or [x["text"] for x in b3.log if "account B failed" in x["text"]]
    check(f"e. {day}: account B raising every poll (inside its pass, and its whole tick) -> LIT's orders identical to B off "
          f"({len(dl(b))} entries, delay {dl(b)} s vs {dl(b2)} s), no poll failed, the error logged",
          sig(b) == sig(b2) and sig(b3) == sig(b2) and not errors and not e3 and bool(err) and bool(err3)
          and all(abs(a - c) <= 3.0 for a, c in zip(dl(b), dl(b2))), (sig(b), sig(b2), errors[:2], err[:1]))


# ------------------------------------------------------------------------------------------------ f. restart
def part_f(H):
    print("f. restart mid-trade on account B", flush=True)
    day = "2026-10-02"
    u = H.ref.sec["ema_lon_vix"][day][0]
    wakes = poll_times(H, day)
    cut = int(u["entry_t"]) + 12 * 60
    ab = ab_block("builder25k", day)
    b, fake = bot_b(H, "rs_" + day, at(day, 1, 45), ab)
    errors = []
    run(H, b, fake, [w for w in wakes if w < cut], errors)
    o1 = (b.acct_b.open_t, (b.acct_b.position() or {}).get("key"))
    b.stop()
    b2, _ = bot_b(H, "rs_" + day, cut, ab, fake=fake)
    o2 = (b2.acct_b.open_t, (b2.acct_b.position() or {}).get("key"))
    run(H, b2, fake, [w for w in wakes if w >= cut], errors)
    x = [r for r in b2.acct_b.ledger if r.get("side") == "exit" and r.get("entry_t") == int(u["entry_t"])]
    recon = [r for r in b2.ledger + b2.acct_b.ledger if r.get("reason") == "RECONCILE"]
    check(f"f. {day}: restart at {hm(cut)} with B's EMA trade open -> recognised ({o2[1]} @ {hm(o2[0]) if o2[0] else None})",
          o1 == o2 and o2[1] == "ema_lon_vix", (o1, o2))
    check(f"f. after the restart B's trade is managed to its exit ({kind_reason(u['exit_kind'])}), no RECONCILE, Sim102 flat",
          len(x) == 1 and x[0]["reason"] == kind_reason(u["exit_kind"]) and not recon and not errors and b2.acct_b.open_t is None
          and not fake.pos.get(("Sim102", next((i for a, i in fake.pos if a == "Sim102"), None)), [0])[0], (x, recon[:2], errors[:2]))


def main():
    quick = "--quick" in sys.argv
    t_all = time.time()
    ref = Ref()
    tmp = tempfile.mkdtemp(prefix="le_acctb_units_")
    try:
        units(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    H = Harness(ref)
    H._fake = None
    install_factory(H)
    out = {"days": []}
    try:
        part_a(H, quick)
        print("b/c. account B on (Sim102) next to LIT (Sim101)", flush=True)
        days = [("2026-10-02", "builder25k", {"expect_same": True})]
        if not quick:
            days += [("2026-08-19", "builder50k", {"expect_same": True}), ("2026-09-04", "builder25k", {}),   # LIT's SHORT is armed at B's 03:10 LONG: blocked

                     ("2026-10-06", "builder50k", {"expect_hedge": True}), ("2026-09-18", "builder25k", {"expect_same": True}),
                     ("2026-10-07", "builder50k", {"expect_same": True})]
        for d, plan, kw in days:
            r = b_day(H, d, plan, f"b. {d} {plan}", **kw)
            out["days"].append({k: v for k, v in r.items() if k != "bot"})
            print(f"     {d} {plan}: {r['rows']} ({r['seconds']} s)", flush=True)
        if not quick:
            # the pass lock on a live day: the 25K starts at +$1,450 (prior), its first winner passes it; nothing after
            d = "2026-08-18"                 # EMA SHORT 03:15 target, then S/R LONG 09:40
            b, fake = bot_b(H, "lock_" + d, at(d, 1, 45), ab_block("builder25k", d, prior=1450.0))
            run(H, b, fake, poll_times(H, d), [])
            B = b.acct_b
            ents = [r for r in B.ledger if r.get("side") in ("buy", "sell")]
            blk = [x["text"] for x in b.log if "NOT routed on account B" in x["text"] and "eval passed" in x["text"]]
            check(f"d. {d} 25K at +$1,450: after the first B trade passes the eval ({B.eval_view()['status']}, balance "
                  f"${B.eval_view()['balance']:,.0f}) the next B signal is NOT routed (pass lock)",
                  len(ents) == 1 and B.eval_view()["status"] == "passed" and bool(blk), (ents, blk[:2], B.eval_view()))
        part_e(H)
        if not quick:
            part_f(H)
    finally:
        AB.ADAPTER_FACTORY = None
        H.close()
    n_ok = sum(1 for _, ok in RESULTS if ok)
    out.update(results=[{"name": n, "ok": ok} for n, ok in RESULTS], passed=n_ok, total=len(RESULTS), seconds=round(time.time() - t_all))
    if not quick:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)
    print(f"account B: {n_ok}/{len(RESULTS)} checks passed in {out['seconds']} s")
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
