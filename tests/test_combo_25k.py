"""ATLAS + Zlarior on ONE account, the Builder 25K #2 (engine/combo25.py; built, OFF by default). Sim / fake NinjaTrader only
(engine/ninjatrader._FakeNT on a temp folder: Sim101 = Zlarior's 50K, the bot's own account, LIT alone; Sim252 = the 25K #2,
an extra account of engine/multi_account with the combo switched on by its harness key "combo"). Nothing is ever armed for a
real account; neither data/combo_50k.json nor research/lab/combo_50k.json is written.

    python -X utf8 -m tests.test_combo_25k            # units + the parity replay (2 eval segments) (~15-30 min)
    python -X utf8 -m tests.test_combo_25k --units    # unit checks only (~10 s)
    python -X utf8 -m tests.test_combo_25k --seg 2026-09-02   # units + that segment

 a. OFF = today: no switch / no harness key -> no lane (LiveBot.acct_x == {}); the real bot never reads a harness key; the switch
    file keeps several Names (the 50K AND the 25K #2), --off --account turns one off; a Rapid's Name is refused.
 b. sizing: ATLAS on the 25K = engine/account_b.qty builder25k x 0.5 in the eval (max(1, floor)) = the simulator's Book.size.
 c. PARITY: 2026 sessions bar by bar through the REAL LiveBot (LIT's lit_live loop + ATLAS's engine/second members, fake
    NinjaTrader, the 50K primary + the 25K #2, a fresh eval per segment, the bot restarted every morning on the same state)
    == tools/money/combo_account.Eval on the Builder 25K (Z+A, ATLAS x0.5 in the eval, the research rules) on the same days:
    the same entries taken and skipped on the 25K, the same micros, the same exits and $; never two positions on the 25K.
    The simulator's rule is close_on_opposite (zprio): first in keeps the account for the SAME side; Zlarior the other way
    closes ATLAS first (no hedging across Zlarior's accounts: the 50K's LIT would close it anyway, LIT > ATLAS).
Results -> research/lab/combo_25k_check.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import account_b as AB  # noqa: E402
from engine import combo25 as CX  # noqa: E402
from engine import combo50k as CB  # noqa: E402
from engine import live  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import ninjatrader as nt  # noqa: E402
from tests import test_combo_50k as T5  # noqa: E402
from tests import test_second_route as TR  # noqa: E402
from tests.test_second_route import Harness, at, hm  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "combo_25k_check.json")
RESULTS = TR.RESULTS
check = TR.check
NAME25 = "Sim252"
SEGMENTS = {"default": [("2026-09-02", "2026-09-10"), ("2026-10-02", "2026-10-07")],
            "full": [("2026-08-18", "2026-09-01"), ("2026-09-02", "2026-09-10"), ("2026-10-02", "2026-10-07")]}


class Reference(T5.Reference):
    """tools/money/combo_account.Eval on the Builder 25K: Zlarior + ATLAS, own sizing, ATLAS x a_f in the eval."""

    def book(self, a_f=0.5, conflict="zprio"):
        C = self.C
        cell = {**C.R("b25", "Z+A"), "conflict": conflict, "a_f": {"eval": a_f, "funded": 1.0}}
        return C.Eval(cell, "Z+A")

    def segment(self, a, z, drop=frozenset(), a_f=0.5, conflict="zprio"):
        ev = self.book(a_f, conflict)
        rows, cands, end = [], {}, None
        for si, day in enumerate(self.S):
            if day < a or day > z:
                continue
            ts = [t for t in self.D[si] if (t["s"], int(t["et"])) not in drop]
            cands[day] = list(self.D[si])
            keep = []
            r, _ = ev.step(ts, keep)
            for t, q, pnl in keep:
                rows.append((day, t["s"], int(t["et"]), int(t["d"]), int(q), round(float(pnl), 2), t["x"], int(t["xt"])))
            if r:
                end = (day, r)
                break
        return rows, cands, end


# ================================================================================================ unit checks
class _Router:
    def __init__(self, real):
        self._real = real

    def real_bot(self):
        return self._real


class _Acc:
    def __init__(self, real=False, **spec):
        self.id, self.name, self.problem = spec.get("id", "z25b"), spec.get("name", "Zlarior 25K #2"), None
        self.spec = {"preset": "mffu_builder_25k", "adapter": "ninjatrader", "nt_account": NAME25, "mode": "two_week", **spec}
        self.router = _Router(real)


def units():
    print("unit checks", flush=True)
    tmp = tempfile.mkdtemp(prefix="le_combo25_")
    try:
        rules = T5.research_cfg()
        check("a. OFF: an extra account without the harness key / the switch -> no combo spec", CX.spec_for(None, _Acc()) is None
              and CX.spec_for(None, _Acc(real=True, combo=rules)) is None if not CB.switch_on_for(NAME25) else True)
        sp = CX.spec_for(None, _Acc(combo=rules))
        check("a. harness key on the 25K #2: on, plan builder25k, first_in, ATLAS x0.5 eval / x1.0 funded, the 3 members",
              bool(sp and sp.get("on")) and sp["plan"] == "builder25k" and sp["conflict"] == "first_in"
              and sp["atlas_size_factor"] == {"eval": 0.5, "funded": 1.0} and sp["keys"] == list(CB.MEMBERS), sp)
        check("a. a Rapid lane / a non-Builder preset never gets the combo",
              CX.spec_for(None, _Acc(combo=rules, lane="rapid")) is None
              and "off_why" in (CX.spec_for(None, _Acc(combo=rules, preset="lucid_pro_50k")) or {}))
        ok = lambda: (True, "ok")
        r1 = CB.set_on("Sim101", "I ACCEPT LIVE RISK", root=tmp, selftest=ok, today="2026-11-23")
        r2 = CB.set_on(NAME25, "I ACCEPT LIVE RISK", root=tmp, selftest=ok, today="2026-11-23")
        sw = CB.read_switch(tmp)
        check("a. the switch holds BOTH Names (the 50K, then the 25K #2); each typed with the phrase",
              r1["ok"] and r2["ok"] and sw["on"] and sw["accounts"] == ["Sim101", NAME25] and sw["account"] == "Sim101"
              and CB.switch_on_for(NAME25, tmp) and CB.switch_on_for("Sim101", tmp), sw)
        r3 = CB.set_on("Sim999", "nope", root=tmp, selftest=ok)
        check("a. no phrase: refused, the list unchanged", not r3["ok"] and CB.read_switch(tmp)["accounts"] == ["Sim101", NAME25], r3)
        CB.set_off(root=tmp, account="Sim101", today="2026-11-23")
        sw2 = CB.read_switch(tmp)
        check("a. --off --account turns ONE Name off (the other stays on)", sw2["on"] and sw2["accounts"] == [NAME25], sw2)
        CB.set_off(root=tmp, today="2026-11-23")
        check("a. --off: every Name off", CB.read_switch(tmp)["on"] is False and not CB.switch_on_for(NAME25, tmp))
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        json.dump({"account": "SimRapid1"}, open(os.path.join(tmp, "data", "rapid.json"), "w"))
        r4 = CB.set_on("SimRapid1", "I ACCEPT LIVE RISK", root=tmp, selftest=ok)
        check("a. a Rapid EOD's Name is refused (ATLAS has its own lane there)", not r4["ok"] and "Rapid" in r4["error"], r4)
        json.dump({"on": True, "account": "Sim101"}, open(os.path.join(tmp, CB.SWITCH_REL), "w"))
        check("a. a switch file of the first build (one 'account') reads as that one Name",
              CB.read_switch(tmp)["accounts"] == ["Sim101"] and not CB.switch_on_for(NAME25, tmp))
        # b. ATLAS's size on the 25K == the simulator's Book.size (account_b.qty builder25k, x0.5 floor, min 1)
        import combo_account as C
        ev = C.Eval({**C.R("b25", "Z+A"), "conflict": "first", "a_f": {"eval": 0.5, "funded": 1.0}}, "Z+A")
        combo = {**sp, "account": NAME25}
        bad, n = [], 0
        for room, prof in ((1000.0, 0.0), (700.0, 300.0), (450.0, -200.0), (950.0, 900.0)):
            for risk in (6.0, 12.5, 20.0, 31.25):
                st = {"profit": prof, "cum": 0.0, "room": room, "session": 3, "n_today": 0, "wk_pnl": 0.0, "days_traded": 2}
                tr = {"risk_pts": risk, "tgt_pts": 2.5 * risk}
                q_ref = int(AB.qty(ev.P["a_spec"], tr, dict(st))["qty"])
                q_ref = max(1, int(q_ref * 0.5 + 1e-9)) if q_ref > 0 else 0
                q = int(CB.atlas_qty(combo, tr, dict(st), "2026-09-02", base=None, stage="eval")["qty"])
                n += 1
                if q != q_ref:
                    bad.append((room, prof, risk, q, q_ref))
        check(f"b. ATLAS's micros on the 25K == the simulator's (account_b.qty builder25k x0.5) on {n} trades x states", not bad, bad)
        check("b. the 25K's ATLAS cap is 20 micros (the plan's)", int(CB.atlas_qty({**combo, "atlas_size_factor": {"eval": 2.0, "funded": 1.0}},
              {"risk_pts": 1.0, "tgt_pts": 3.0}, {"profit": 0.0, "cum": 0.0, "room": 1000.0, "session": 1, "n_today": 0},
              "2026-09-02", stage="eval")["qty"]) <= 20)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ the parity replay
def day_bot(H, seg_dir, day, eval_start, rules):
    """The PC bot's morning start on `day`: Sim101 (the 50K, LIT alone) + the extra account Sim252 (the 25K #2, combo on)."""
    d = os.path.join(H.tmp, seg_dir)
    nd = os.path.join(d, day)
    folder = os.path.join(nd, "NinjaTrader 8")
    fake = nt._FakeNT(folder, price=25000.0)
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
    acc = {"id": "z25b", "name": "Zlarior 25K #2", "adapter": "ninjatrader", "nt_account": NAME25, "preset": "mffu_builder_25k",
           "mode": "two_week", "eval_start": eval_start, "armed": False, "combo": rules}
    start_t = at(day, 1, 45)
    H.rp.now = int(start_t)
    H.clock.base, H.clock.running = float(start_t), False
    b = live.LiveBot()
    b.clock = H.clock
    b.read_hist, b.fetch_recent = H.rp.read_hist, H.rp.fetch_recent
    b.state_path = os.path.join(d, "live_state.json")
    b._remember = lambda *a_, **kw: None
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "nt_folder": folder, "nt_account": "Sim101",
           "model": "lit", "model_params": H.ref.lit_p, "params": {"max_micros": 40, "flat_mod": 955},
           "nt_state_path": os.path.join(nd, "nt_state.json"), "nt_audit_log": os.path.join(nd, "oif.log"),
           "eval_start": eval_start, "accounts": [acc], "accounts_parallel": False, "account_b": None, "account_c": None,
           "fleet": None}
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    ad = b.adapter
    ad.clock = clock
    ad._alert_fn = lambda *a_, **kw: None
    ad._sleep = nt_sleep
    return b, fake


def live_rows(b, day):
    """The 25K #2's trades of `day`: [(day, s, entry_t, dir, qty, pnl, reason)] (Z = its LIT lane, A = ATLAS's combo lane)."""
    out = []
    acc = next(a for a in b.accts.accounts if a.id == "z25b")
    lane = (b.acct_x or {}).get("z25b")
    for s, obj in (("Z", acc), ("A", lane)):
        if obj is None:
            continue
        cl = {int(c[3]): float(c[2]) for c in obj.closes if len(c) > 3}
        for e in obj.ledger:
            if e.get("side") not in ("buy", "sell") or not e.get("entry_t") or live.trading_day(int(e["entry_t"])) != day:
                continue
            if (e.get("result") or {}).get("ok") is False:
                continue
            x = [r for r in obj.ledger if r.get("side") == "exit" and r.get("entry_t") == e["entry_t"]]
            out.append((day, s, int(e["entry_t"]), 1 if e["side"] == "buy" else -1, int(e["qty"]), round(cl.get(int(e["entry_t"]), 0.0), 2),
                        x[-1].get("reason") if x else None, e.get("who")))
    return out


def one_position_25k(b):
    """Never an entry of either lane on the 25K while the other lane's (or its own) earlier entry is still open."""
    acc = next(a for a in b.accts.accounts if a.id == "z25b")
    lane = (b.acct_x or {}).get("z25b")
    ev = []
    for obj in (acc, lane):
        if obj is None:
            continue
        for r in obj.ledger:
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


def run_segment(H, R, a, z, rules, label):
    rows_ref, cands, end = R.segment(a, z)
    days = sorted(cands)
    if end:
        days = [d for d in days if d <= end[0]]
    seg = f"seg25_{a}"
    rows_live, errors, two_pos, logs, fake_max = [], [], [], [], 0
    t0 = time.time()
    for day in days:
        cs = cands.get(day) or []
        if not cs:
            continue
        b, fake = day_bot(H, seg, day, a, rules)
        errs = []
        mx = [0]

        def on_poll(bot, w, fake=fake, mx=mx):
            q = sum(abs(q) for (ac, _), (q, _x) in fake.pos.items() if ac == NAME25)
            mx[0] = max(mx[0], len([1 for (ac, _), (q2, _x) in fake.pos.items() if ac == NAME25 and q2]))
        H.run(b, fake, T5.poll_times(day, cs), errs, on_poll=on_poll)
        fake_max = max(fake_max, mx[0])
        errors += [f"{day} {e}" for e in errs]
        rows_live += live_rows(b, day)
        bad = one_position_25k(b)
        if bad:
            two_pos.append((day, bad))
        logs += [f"{day} {x['text']}" for x in b.log if ("25K" in x["text"] or NAME25 in x["text"] or "ATLAS on" in x["text"])]
        if not b.acct_x:
            errors.append(f"{day} the combo lane did not start: " + "; ".join(x["text"] for x in list(b.log)[:30] if "combo" in x["text"].lower() or "ATLAS" in x["text"]))
        b.stop()
        print(f"   {label} {day}: {len([r for r in rows_live if r[0] == day])} trade(s) on the 25K, {time.time() - t0:.0f} s", flush=True)
    return rows_live, rows_ref, {"end": end, "errors": errors, "two_pos": two_pos, "logs": logs[-300:], "fake_max": fake_max,
                                 "seconds": round(time.time() - t0)}


def compare(rows_live, rows_ref, label, det):
    key = lambda r: (r[1], r[2])
    L = {key(r): r for r in rows_live}
    F = {key(r): r for r in rows_ref}
    check(f"{label}: the same entries taken (and so the same skipped) on the 25K as the simulator: {len(F)} trades "
          f"({sum(1 for r in rows_ref if r[1] == 'Z')} Zlarior, {sum(1 for r in rows_ref if r[1] == 'A')} ATLAS)", set(L) == set(F),
          {"live_only": [(k[0], hm(k[1])) for k in sorted(set(L) - set(F))], "ref_only": [(k[0], hm(k[1])) for k in sorted(set(F) - set(L))]})
    both = sorted(set(L) & set(F), key=lambda k: k[1])
    side = [(k[0], hm(k[1]), L[k][3], F[k][3]) for k in both if L[k][3] != F[k][3]]
    qty = [(k[0], hm(k[1]), L[k][4], F[k][4]) for k in both if L[k][4] != F[k][4]]
    check(f"{label}: the same side and micros on every common trade", not side and not qty, {"side": side, "qty": qty})
    usd = [(k[0], hm(k[1]), L[k][5], F[k][5], L[k][6], F[k][6]) for k in both
           if abs(L[k][5] - F[k][5]) > max(0.06, 0.02 * F[k][4]) and F[k][6] != "cut"]
    check(f"{label}: the same exit $ on every common trade (booked on the 25K = the simulator's $ at those micros)", not usd, usd)
    lab = [(k[0], hm(k[1])) for k in both if L[k][1] == "A" and L[k][7] != CX.label_of(type("A", (), {"name": "Zlarior 25K #2"}))]
    check(f"{label}: every ATLAS entry on the 25K says who traded it ('ATLAS on Zlarior 25K #2')", not lab, lab)
    check(f"{label}: never two positions on the 25K (ledger order; the fake NinjaTrader never holds 2 positions there)",
          not det["two_pos"] and det["fake_max"] <= 1, (det["two_pos"][:3], det["fake_max"]))
    check(f"{label}: no error in the live loop", not det["errors"], det["errors"][:3])
    return {"live": len(L), "ref": len(F), "end": det["end"], "seconds": det["seconds"],
            "rows": [{"day": r[0], "bot": r[1], "entry": hm(r[2]), "dir": r[3], "qty": r[4], "usd": r[5], "exit": r[6]}
                     for r in sorted(rows_live, key=lambda r: r[2])],
            "ref_rows": [{"day": r[0], "bot": r[1], "entry": hm(r[2]), "dir": r[3], "qty": r[4], "usd": r[5], "exit": r[6]}
                         for r in sorted(rows_ref, key=lambda r: r[2])]}


def replay(segments):
    print("parity replay: the real LiveBot (50K primary + the 25K #2 with Zlarior + ATLAS) vs tools/money/combo_account.Eval b25",
          flush=True)
    R = Reference()
    ref = TR.Ref()
    H = Harness(ref, lm_extra={"lit_sizing": T5.lit_sizing()})
    rules = T5.research_cfg()
    out = {}
    try:
        for a, z in segments:
            label = f"c. 25K #2 eval from {a} (the research rules: ATLAS x0.5 in the eval)"
            rl, rr, det = run_segment(H, R, a, z, rules, label)
            out[a] = compare(rl, rr, label, det)
            out[a]["logs"] = det["logs"][-80:]
            print(f"   {label}: {out[a]['live']} live / {out[a]['ref']} reference trades, eval end {det['end']}, {det['seconds']} s",
                  flush=True)
    finally:
        MA.ADAPTER_FACTORY = None
        AB.ADAPTER_FACTORY = None
        H.close()
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    t0 = time.time()
    units()
    out = {}
    if "--units" not in argv:
        segs = SEGMENTS["full" if "--full" in argv else "default"]
        if "--seg" in argv:
            day = argv[argv.index("--seg") + 1]
            segs = [x for x in SEGMENTS["full"] if x[0] == day][:1]
        out = replay(segs)
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n_ok}/{len(RESULTS)} checks passed ({time.time() - t0:.0f} s)")
    if out:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "checks": f"{n_ok}/{len(RESULTS)}", "segments": out}, fh, indent=1, default=str)
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
