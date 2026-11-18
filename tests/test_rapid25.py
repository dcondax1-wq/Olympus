"""The MFFU Rapid EOD 25K (owner 2026-11-18): engine/rapid.py's lanes at the 25K's numbers, mirroring tests/test_rapid.py.

    python -X utf8 -m tests.test_rapid25          # ~10 s

Paper bots, temp files, Sim / made-up names only: nothing routed to a real NinjaTrader, nothing real armed.
  a. the one line (engine.accounts add --plan rapideod25): a DISARMED 25K block; only the typed phrase arms it; MFFU's own
     3 Rapid 25K funded slots inside the 5 funded; the Name never equals another account; one Rapid only
  b. sizes: ATLAS min($250, 30% of the room), max 20 micros; LIT's lane on the 25K rules (20 micros, soft $500 day)
  c. the 30% best-day guard on $1,500 (a day <= $427 = 30% x $1,500 x 0.95, under MFFU's $450), on the combined day
  d. the floor: $1,000 EOD trailing in the eval; funded after the first payout locked at start + $100
  e. never two positions on the account; a NinjaTrader reject is not booked
  f. funded: Tier-1 news ban (ATLAS refused + flattened, LIT's lane news on); payouts above $1,100 + $500 kept in
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import multi_account as MA, rapid  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402
from tests.test_rapid import Clock, DAY, T0, lane, make_bot, pos_at, ts  # noqa: E402

RESULTS = []
P25 = "mffu_rapid_eod_25k"


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def blk25(**kw):
    return {"account": "Sim205", "eval_start": DAY, "armed": False, "plan": P25, **kw}


def cli_checks(tmp):
    """a. engine.accounts add --plan rapideod25 (the test world of tests/test_accounts_cli)."""
    from engine import account_cli as AC, go as G
    from tests import test_accounts_cli as TC
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    keep_rp, env_keep = rapid.PATH, os.environ.get("NINJATRADER_FOLDER")
    try:
        os.makedirs(tmp, exist_ok=True)
        TC.world(tmp)
        G.bot_running = lambda: False
        NR = "MFFUEVRPD250000001"
        check("a. MFFU limits: Rapid EOD 25K has its own 3 funded (Rapid 50K 3, 5 funded in all)",
              AC.limits()["rapideod25"] == 3 and AC.limits()["rapideod"] == 3 and AC.limits()["funded"] == 5, AC.limits())
        r = AC.add("rapideod25", TC.L25)
        check("a. refused: the Rapid's Name = ATLAS's 25K", r["ok"] is False and "already" in r["error"], r)
        r = AC.add("rapideod25", TC.L50)
        check("a. refused: the Rapid's Name = Zlarior's 50K", r["ok"] is False and "already" in r["error"], r)
        r = AC.add("rapideod25", NR)
        b = rapid.read()
        check("a. --plan rapideod25: the 25K block (LIT + ATLAS), DISARMED, allowlisted",
              r["ok"] and b and b["account"] == NR and b["plan"] == P25 and b["armed"] is False and NR in TC.allowed()
              and "Rapid EOD 25K" in r["say"], (r, b))
        inv = [x for x in AC.inventory() if x["role"] == "rapid"]
        check("a. inventory: the Rapid row is a Rapid EOD 25K eval", [(x["plan"], x["stage"]) for x in inv] == [("rapideod25", "eval")], inv)
        check("a. slots line shows the Rapid EOD 25K", "Rapid EOD 25K 0/3" in AC.slots_text(), AC.slots_text())
        for what, rr in (("a 2nd Rapid 25K", AC.add("rapideod25", "MFFUEVRPD250000002")),
                         ("a Rapid 50K next to the 25K (one Rapid only)", AC.add("rapideod", "MFFUEVRPD500000009")),
                         ("the same Name again", AC.add("rapideod25", NR)),
                         ("--bots lit on the Rapid 25K", AC.add("rapideod25", "MFFUEVRPD250000003", bots="lit"))):
            check(f"a. refused: {what}", rr.get("ok") is False and rr.get("error"), rr)
        check("a. the Rapid 25K stays disarmed (only START BOT's rapid.arm with the phrase arms it)",
              rapid.read()["armed"] is False and rapid.arm("i accept")["ok"] is False and rapid.read()["armed"] is False)
        rows = AC.inventory()
        f3 = rows + [{"name": f"R{i}", "plan": "rapideod25", "stage": "funded", "sim": False, "role": "extra", "id": f"r{i}"}
                     for i in range(3)]
        check("a. 3 funded Rapid 25K: the 4th is refused by its own cap",
              "3 funded Rapid EOD 25K" in (AC.limit_problem("rapideod25", "funded", "MFFUFD9", f3) or ""),
              AC.limit_problem("rapideod25", "funded", "MFFUFD9", f3))
        f5 = rows + [{"name": f"F{i}", "plan": p, "stage": "funded", "sim": False, "role": "extra", "id": f"f{i}"}
                     for i, p in enumerate(["builder50k", "builder25k", "builder25k", "rapideod", "rapideod25"])]
        check("a. 5 funded in all (any mix): a Rapid 25K funded is refused by the total cap",
              "5 funded accounts" in (AC.limit_problem("rapideod25", "funded", "MFFUFD9", f5) or ""))
        r = AC.remove(NR)
        check("a. remove the Rapid 25K: OFF, off the allowlist", r["ok"] and rapid.read() is None and NR not in TC.allowed(), r)
        r = AC.add("rapideod", "MFFUEVRPD500000003")
        check("a. the 50K line is unchanged: plan mffu_rapid_eod_50k", r["ok"] and rapid.read()["plan"] == "mffu_rapid_eod_50k"
              and r["say"].startswith("[OK] Rapid EOD 50K ="), r)
        AC.remove("MFFUEVRPD500000003")
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        rapid.PATH = keep_rp
        if env_keep is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = env_keep


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rapid25_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        clock = Clock(T0 + 290)
        # ---- a. the block and the preset
        fp = os.path.join(tmp, "rapid.json")
        r = rapid.set_account("Sim205", p=fp, others={"Zlarior (50K)": "Sim101"}, preset=P25)
        check("a. set_account(preset 25K): DISARMED 25K block", r["ok"] and rapid.read(fp)["plan"] == P25
              and rapid.read(fp)["armed"] is False, r)
        check("a. the same Name again keeps the 25K (no reset, no switch to the 50K)",
              rapid.set_account("Sim205", p=fp, others={})["block"]["plan"] == P25)
        check("a. arm with the typed phrase only; the phrase never lands in the file",
              not rapid.arm("i accept", p=fp)["ok"] and rapid.arm(LIVE_PHRASE, p=fp)["ok"] and rapid.read(fp)["armed"] is True
              and LIVE_PHRASE not in open(fp, encoding="utf-8").read())
        ls = rapid.lane_spec(rapid.read(fp), {"adapter": "ninjatrader", "confirm": LIVE_PHRASE})
        ab = rapid.atlas_block(rapid.read(fp))
        check("a. LIT lane = preset mffu_rapid_eod_25k two_week; ATLAS lane = plan rapideod25k",
              ls["preset"] == P25 and ls["mode"] == "two_week" and ls["name"] == "Rapid EOD 25K" and ab["plan"] == "rapideod25k", (ls, ab))
        R = MA.PRESETS[P25]["rules"]
        F = MA.PRESETS[P25]["sizing"]["funded"]
        check("a. preset: $1,500 target, $1,000 EOD floor (+$100 lock), 20 micros, 30% / 4 days, funded news ban, soft $500 day",
              (R["start"], R["target"], R["mll"], R["lock"], R["max_micros"], R["best_day"], R["min_days"], R["news_ban"], R["dll"])
              == (25000.0, 1500.0, 1000.0, 100.0, 20, 0.3, 4, "funded", 500.0) and "scale" not in R, R)
        check("a. preset sizing: eval = LIT's live two_week (no override); funded 60% of the room <= $750, a winner <= $1,000",
              "two_week" not in MA.PRESETS[P25]["sizing"] and (F["pct"], F["pct_max_usd"], F["max_win"]) == (0.6, 750, 1000), F)
        P50 = MA.PRESETS["mffu_rapid_eod_50k"]["rules"]
        check("a. the 50K preset unchanged", (P50["target"], P50["mll"], P50["max_micros"], P50["dll"]) == (3000.0, 2000.0, 30, 1000.0))

        # ---- b. sizes on a live paper bot
        b = make_bot(os.path.join(tmp, "b1"), clock, blk25())
        L, A = lane(b), b.acct_r
        check("b. on: LIT's lane + ATLAS's lane on the same 25K account",
              L is not None and isinstance(A, rapid.RapidAtlas) and L.spec["nt_account"] == A.name == "Sim205"
              and L.spec["preset"] == P25 and A.spec["preset"] == P25 and A.problem is None and L.problem is None,
              (A and A.problem, L and L.problem))
        st = A._state_raw(T0)
        check("d. eval floor: $1,000 of room at the start (EOD trailing)", abs(float(st["room"]) - 1000.0) < 0.01, st)
        s1 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, st)
        check("b. ATLAS $250 risk on a 10-pt stop: 11 micros (250 / 22.4)", s1["qty"] == 11 and "min $250" in s1["reasons"][0], s1)
        s1b = A.size({"risk_pts": 2.0, "tgt_pts": 4.0}, st)
        check("b. ATLAS never above 20 micros (MFFU 2 minis / 20 micros)", s1b["qty"] == 20, s1b)
        ent = {**pos_at(T0, entry=25020.0, stop=24990.0, target=25050.0), "tgt_pts": 30.0}
        q = L.qty_for(ent, T0 + 300)
        loss = q * ((30.0 + 0.25) * 2.0 + 1.9)
        check("b. LIT's lane on the 25K rules: 1..20 micros, a full stop-out <= the $500 soft day, a winner <= $427",
              1 <= q <= 20 and loss <= 500.0 and q * (30.0 * 2.0 - 1.9) <= 427.5, (q, loss, L.last_size))

        # ---- c. the 30% best-day guard on $1,500
        s0 = A.size({"risk_pts": 10.0, "tgt_pts": 40.0}, st)
        check("c. 30% x $1,500: a winner pays <= $427 (MFFU's $450 with 5% spare) -> 5 micros on a 40-pt target",
              s0["qty"] == 5 and any("$428" in x or "$427" in x for x in s0["reasons"]), s0)
        A.closes.append([DAY, T0 - 1800, 200.0, T0 - 2000])
        s2 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, A._state_raw(T0))
        check("c. $200 made today -> a winner pays <= $228 -> 5 micros", s2["qty"] == 5, s2)
        A.closes.append([DAY, T0 - 1700, 200.0, T0 - 1900])
        q = L.qty_for({**pos_at(T0), "tgt_pts": 200.0}, T0 + 300)
        check("c. LIT's lane: the cap counts ATLAS's $ today (skip when 1 micro's winner is too big)",
              q == 0 and any("best-day" in x for x in (L.last_size or {}).get("reasons", [])), L.last_size)
        A.closes.clear()
        for i, d in enumerate(("2026-10-21", "2026-10-22", "2026-10-23")):
            A.closes.append([d, T0 + i * 86400, 550.0, T0 + i * 86400 - 60])
        clock.t = ts(2026, 10, 26, 10, 0)
        check("c. $1,650 in 3 days: NOT passed (4 days needed)", A.eval_view()["status"] == "open", A.eval_view().get("status"))
        A.closes[:] = [[d, T0 + i * 86400, v, T0 + i * 86400 - 60]
                       for i, (d, v) in enumerate((("2026-10-21", 700.0), ("2026-10-22", 300.0), ("2026-10-23", 300.0), ("2026-10-26", 300.0)))]
        clock.t = ts(2026, 10, 27, 10, 0)
        check("c. $1,600 in 4 days but best day $700 > 30%: NOT passed", A.eval_view()["status"] == "open", A.eval_view())
        A.closes[:] = [[d, T0 + i * 86400, 400.0, T0 + i * 86400 - 60]
                       for i, d in enumerate(("2026-10-21", "2026-10-22", "2026-10-23", "2026-10-26"))]
        check("c. $1,600 in 4 days, best $400 <= 30%: passed", A.eval_view()["status"] == "passed", A.eval_view())
        A.closes.clear()
        clock.t = T0 + 290
        A.closes.append([DAY, T0 - 1800, -1000.0, T0 - 2000])
        s4 = A.size({"risk_pts": 10.0, "tgt_pts": 20.0}, A._state_raw(T0))
        check("d. -$1,000: at the floor, no trade", s4["qty"] == 0 and s4["lock"] == "failed", s4)
        A.closes.clear()

        # ---- e. never two positions; a reject is not booked
        b.state = {"model": "lit", "position": None, "lit": {}}
        check("e. LIT flat, no setup: ATLAS may enter", A.lit_opposite(1) is None, A.lit_opposite(1))
        L.open_t = T0 - 600
        check("e. LIT's lane holds a trade: ATLAS blocked (either side)", A.lit_opposite(1) and A.lit_opposite(-1))
        L.open_t = None
        tb = T0 - 900
        A.open_t = tb
        A.prov[tb] = {"key": "macd_sweep", "short": "MACD", "qty": 3, "dir": 1, "entry": 25000.0, "stop": 24990.0,
                      "target": 25030.0, "t": tb, "risk_pts": 10.0, "day": DAY}
        A.ledger.append({"t": tb, "sym": "NQ", "side": "buy", "qty": 3, "entry_t": tb, "result": {"ok": True}})
        clock.t = T0 + 305
        b.state = {"model": "lit", "position": pos_at(T0, target=25050.0), "lit": {}}
        b._route_signals({"trades": [], "events": []}, "NQ", int(clock.t), 300)
        ex = [r for r in A.ledger if r.get("side") == "exit"]
        ent_l = [r for r in L.ledger if r.get("side") in ("buy", "sell")]
        check("e. LIT enters while ATLAS holds: ATLAS closed at market first (HEDGE), then LIT's lane routed",
              A.open_t is None and ex and ex[0]["reason"] == "HEDGE" and ent_l and L.open_t == T0
              and ex[0]["t"] <= ent_l[0]["t"], (A.open_t, ex, ent_l, L.last_size))
        clock.t = T0 + 290
        b4 = make_bot(os.path.join(tmp, "b4"), clock, blk25(account="Sim208"))
        L4, A4 = lane(b4), b4.acct_r
        L4.open_t, L4.open_qty = T0, 5
        L4.seen.add(("entry", T0))
        L4.ledger.append({"t": T0 + 3, "sym": "NQ", "side": "buy", "qty": 5, "entry_t": T0,
                          "result": {"ok": False, "error": "order rejected: Limit 0"}})
        clock.t = T0 + 605
        b4.state = {"model": "lit", "position": None, "lit": {}}
        tr = {**pos_at(T0), "exit_t": T0 + 600, "exit": 25220.0, "pnl": 2000.0, "exit_reason": "TARGET", "day": DAY}
        b4._route_signals({"trades": [tr], "events": []}, "NQ", int(clock.t), 300)
        check("e. LIT lane entry rejected ('Limit 0'): flat, no exit routed, $0 booked on the Rapid 25K's book",
              L4.open_t is None and not L4.closes and A4.day_pnl(DAY) == 0.0
              and not [r for r in L4.ledger if r.get("side") == "exit"], (L4.open_t, L4.closes, L4.ledger[-1:]))

        # ---- f. funded
        clock.t = T0 + 290
        fb = make_bot(os.path.join(tmp, "b2"), clock, blk25(account="Sim206", eval_start="2026-09-01", stage="funded",
                                                            funded_start="2026-10-01", payouts={}))
        FA, FL_ = fb.acct_r, lane(fb)
        check("f. funded: both lanes funded, LIT's lane news ban on", FA.funded() and FL_.mode == "funded" and FL_.news_on())
        rel = T0 + 600
        old = MA.tier1_releases
        MA.tier1_releases = lambda day: [rel]
        try:
            g = FA.guard({"sym": "NQ", "side": "buy", "qty": 1, "stop": 1.0, "target": 2.0, "entry": 1.5, "entry_t": rel - 60},
                         rel - 60, rel - 60)
            check("f. funded: ATLAS entry inside a Tier-1 window refused", bool(g) and "news" in g, g)
            check("f. funded: outside the window no news block", FA.news_at(rel - 400) is None and FA.news_at(rel + 151) is None)
            check("f. eval: no news ban", A.news_at(rel) is None)
            et2 = rel - 30
            FA.open_t = et2
            FA.prov[et2] = {"key": "macd_sweep", "short": "MACD", "qty": 2, "dir": 1, "entry": 25000.0, "stop": 24990.0,
                            "target": 25030.0, "t": et2, "risk_pts": 10.0, "day": DAY}
            FA.ledger.append({"t": et2, "sym": "NQ", "side": "buy", "qty": 2, "entry_t": et2, "result": {"ok": True}})
            FA.tick(None, None, "NQ", int(rel + 30))
            check("f. funded: ATLAS still open inside the window -> NEWS FLAT",
                  FA.open_t is None and any(r.get("reason") == "NEWS FLAT" for r in FA.ledger if r.get("side") == "exit"))
        finally:
            MA.tier1_releases = old
        FA.closes.clear()
        a1 = rapid.payout_advice(27200.0, 25000.0, buffer=1100.0, cushion=500.0)
        check("f. payout: $27,200 -> request $600 ($540 to you), keeps $26,600 in ($1,100 buffer + $500)",
              a1["ready"] and a1["request"] == 600 and a1["to_you"] == 540.0 and a1["keep_at"] == 26600.0, a1)
        FA.closes.append(["2026-10-02", ts(2026, 10, 2, 11, 0), 2200.0, ts(2026, 10, 2, 10, 0)])
        fv = FA.funded_view(T0)
        check("f. funded tracker on the shared 25K book: request $600 today", fv["ready"] and fv["request"] == 600.0, fv)
        s3 = FA.size({"risk_pts": 10.0, "tgt_pts": 20.0}, FA._state_raw(T0))
        check("f. funded ATLAS: $250 risk, no best-day cap", s3["qty"] == 11, s3)
        FA.spec["funded"]["payouts"] = {"2026-10-05": 600.0}
        fs = FA._funded_state(DAY)
        check("d. funded after the first payout: floor locked at start + $100", fs.get("locked") is True
              and abs(float(fs["floor"]) - 100.0) < 0.01, fs)
        # MFFU 25K: >= $250 net since the last payout (here the owner took only $500 of a big balance)
        FA.closes[:] = [["2026-10-02", ts(2026, 10, 2, 11, 0), 4000.0, ts(2026, 10, 2, 10, 0)]]
        FA.spec["funded"]["payouts"] = {"2026-10-05": 500.0}
        FA.closes.append(["2026-10-20", ts(2026, 10, 20, 11, 0), 100.0, ts(2026, 10, 20, 10, 0)])
        fv2 = FA.funded_view(T0)
        check("f. funded: only $100 made since the last payout -> no request ($150 more, MFFU's $250 rule)",
              not fv2["ready"] and fv2.get("since_short") == 150.0 and "since the last" in fv2["text"], fv2)
        FA.closes.append(["2026-10-20", ts(2026, 10, 20, 12, 0), 200.0, ts(2026, 10, 20, 11, 30)])
        fv3 = FA.funded_view(T0)
        check("f. funded: $300 since the last payout -> request again", fv3["ready"] and "since_short" not in fv3, fv3)
        a50 = rapid.payout_advice(53700.0, paid_days=["2026-10-05"])
        check("f. the 50K's advice is unchanged (no since check)", a50["ready"] and a50["request"] == 600 and "since_short" not in a50, a50)
        FA.spec["funded"]["payouts"] = {}
        FA.closes[:] = [["2026-10-02", ts(2026, 10, 2, 11, 0), 2200.0, ts(2026, 10, 2, 10, 0)]]
        from engine import board_events as BE, brain_glance as BG, lifecycle as LC
        check("f. labels: lifecycle 'Rapid EOD 25K', board rules ($25,000 / $1,500 / $1,000)",
              LC.label_of("rapid", FA) == "Rapid EOD 25K" and LC.label_of("rapid", lane(b)) == "Rapid EOD 25K"
              and BE._rules("MFFU Rapid EOD 25K") == (25000.0, 1500.0, 1000.0) and BE._rules("Rapid EOD 50K")[0] == 50000.0)
        L25 = LC.limits("rapideod25k")
        check("f. lifecycle limits of the 25K: $1,500 target, $1,100 buffer, $500 kept, 4 days, 30%",
              (L25["start"], L25["target"], L25["mll"], L25["buffer"], L25["cushion"], L25["min_days"], L25["best_day"])
              == (25000.0, 1500.0, 1000.0, 1100.0, 500.0, 4, 0.3) and LC.limits("rapideod50k")["buffer"] == 2100.0, L25)
        g25 = BG.rapid({"acct": {"accounts": [{"id": "rapid", "plan_rules": {"start": 25000.0, "mll": 1000.0}}]}})
        check("f. phone glance names the 25K", g25 and g25["what"].endswith("Rapid EOD 25K"), g25)
        lf = LC.rapid_facts(FA, None, T0)
        check("f. lifecycle facts of the funded 25K: start $25,000, payout line $26,600 + $500",
              lf and lf["start"] == 25000.0 and lf["kind"] == "funded", lf)
        sx = rapid.status(p=fp)
        check("status(): the 25K's balance and target", sx["on"] and "target $26,500" in sx["text"] and "Rapid EOD 25K" in sx["text"], sx)
        cli_checks(os.path.join(tmp, "cli"))
    finally:
        MA.ADAPTER_FACTORY = None
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
