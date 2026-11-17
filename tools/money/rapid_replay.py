"""Replay Jul-Oct 2026 through the LIVE Rapid EOD code (engine/rapid.py + engine/multi_account LIT lane) - paper only.

The trades are the stored ones of research/writeups/stack-one-account-2026-11-16.md (LIT: the 2026 live trades, tools/
account4_sim; ATLAS: tools/atlas.account_units, never opposite LIT), the SIZING, guards and book are the live objects of a
paper LiveBot with a "rapid" block: the LIT lane's Account.entry_block / qty_for (two_week on the Rapid, the 30% best-day cap
on the combined day, the soft $1,000 day, 1 trade a day) and RapidAtlas.lit_opposite / size / eval_view (blocked while LIT
holds, $500 / 30% of the room, the best-day cap, pass = $3,000 + 4 days + best day <= 30%). LIT entering while ATLAS holds
closes ATLAS at that minute (1 tick). Costs $1.90 a micro. Not modelled: the funded news flatten of a trade already open at
release - 2 min (entries inside the window are refused), intraday partial fills.

    python -X utf8 tools/money/rapid_replay.py              # every start session Jul 1 .. Oct, eval + one funded run
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))

PV, COMM, TICK = 2.0, 1.90, 0.25
H2 = ("2026-07-01", "2026-10-31")
OUT = os.path.join(ROOT, "research", "lab", "rapid_replay.json")


class Clock:
    def __init__(self, t=0):
        self.t = t

    def __call__(self):
        return self.t


def _bot(tmp, blk, clock):
    from engine import multi_account as MA
    from engine.live import LiveBot
    MA.ADAPTER_FACTORY = None
    b = LiveBot()
    b.clock = clock
    b.state_path = os.path.join(tmp, "live_state.json")
    b._log = lambda *a, **k: None
    r = b.start({"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955},
                 "accounts_parallel": False, "account_b": None, "account_c": None, "fleet": None, "rapid": blk}, spawn=False)
    assert r.get("ok"), r
    ls = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
    b._lit_sizing = dict(ls)
    b._log = lambda *a, **k: None
    L = next(a for a in b.accts.accounts if a.spec.get("lane") == "rapid")
    for o in (b.accts, b.acct_r):
        o.save = lambda *a, **k: None
    b.acct_r.log = lambda *a, **k: None
    b.accts.log = lambda *a, **k: None
    return b, L, b.acct_r


def trades():
    import stack_one_account as SO
    D = SO.data()
    from tools import atlas as A
    S = D["S"]
    lit = {d: [dict(t, strat="LIT") for t in D["LIT"][i]] for i, d in enumerate(S)}
    at = {}
    for t in A.account_units(A.BASE):
        at.setdefault(t["day"], []).append(dict(t, strat="ATLAS"))
    return S, lit, at


def _po_at(t, when):
    """ATLAS's open P&L in points at minute `when` (its path), minus 1 tick (the market close)."""
    pt, po = t.get("pt"), t.get("po")
    v = 0.0
    if pt is not None:
        for a, b in zip(list(pt), list(po)):
            if int(a) <= int(when):
                v = float(b)
    return v - TICK


def run_eval(b, L, A, clock, sessions, lit, at, funded=False, log=None):
    """One account from sessions[0]. Eval: -> (status, sessions used, $). Funded: payouts recorded at each EOD."""
    from engine import rapid
    from engine.multi_account import trading_day
    L.closes, L.ledger, L.seen, L.lock, L.open_t = [], [], set(), None, None
    A.closes, A.ledger, A.prov, A.lock, A.open_t, A.notified = [], [], {}, None, None, []
    start = sessions[0]
    if funded:
        L.spec["funded"] = {"start": start, "payouts": {}}
        A.spec["funded"] = {**(A.spec.get("funded") or {}), "start": start, "payouts": {}, "prior": 0.0}
        L.spec["funded"]["payouts"] = A.spec["funded"]["payouts"]          # one payouts dict for both lanes
    else:
        L.spec["eval_start"] = A.spec["eval_start"] = start
    pays, first_pay, n_tr = [], None, {"LIT": 0, "ATLAS": 0}
    for k, d in enumerate(sessions):
        evs = sorted(lit.get(d, []) + at.get(d, []), key=lambda t: (t["entry_t"], 0 if t["strat"] == "LIT" else 1))
        a_open = None                                   # (trade, qty)
        a_today = 0
        for t in evs:
            now = int(t["entry_t"]) + 5
            if a_open and int(a_open[0]["exit_t"]) <= int(t["entry_t"]):
                at_, q = a_open
                A._close(int(at_["entry_t"]), int(at_["exit_t"]), round(q * (float(at_["pts"]) * PV - COMM), 2), int(at_["exit_t"]))
                a_open, A.open_t = None, None
            clock.t = now
            dr = 1 if int(t["dir"]) == 1 else -1
            if t["strat"] == "LIT":
                why = L.entry_block(now)
                if why:
                    continue
                e0 = 20000.0
                ent = {"entry_t": int(t["entry_t"]), "dir": dr, "qty": 0, "entry": e0, "stop": e0 - dr * t["risk"],
                       "stop0": e0 - dr * t["risk"], "target": e0 + dr * t["tgt"], "risk_pts": float(t["risk"]),
                       "tgt_pts": float(t["tgt"])}
                from engine.lit import qty_for
                ent["qty"] = int(qty_for(float(t["risk"])) or 0)
                if not ent["qty"]:
                    continue
                q = L.qty_for(ent, now)
                if q <= 0:
                    continue
                if a_open:                               # LIT first: ATLAS closed at market at LIT's entry minute
                    at_, qa = a_open
                    A._close(int(at_["entry_t"]), now, round(qa * (_po_at(at_, t["entry_t"]) * PV - COMM), 2), now)
                    a_open, A.open_t = None, None
                st = L.state(d)
                low = min(0.0, float(t.get("w1") or 0.0) * PV * q - COMM * q)
                if st is not None and st.get("room") is not None and float(st["room"]) + low <= 0:
                    return {"status": "failed" if not funded else "lost", "sessions": k + 1, "day": d, "pays": pays}
                L.ledger.append({"t": now, "sym": "NQ", "side": "buy" if dr == 1 else "sell", "qty": q, "entry_t": ent["entry_t"],
                                 "result": {"ok": True}})
                L._close(int(t["entry_t"]), int(t["exit_t"]), round(q * (float(t["pts"]) * PV - COMM), 2), int(t["exit_t"]), t.get("exit"))
                n_tr["LIT"] += 1
                L.open_t = None
                # LIT held from entry to exit: an ATLAS entry inside that span is blocked below (L busy window)
                L._busy = int(t["exit_t"])
            else:
                if a_open or a_today >= 2 or (getattr(L, "_busy", 0) and int(t["entry_t"]) < L._busy):
                    continue
                if A.lock and A.lock.get("day") == d:
                    continue
                if funded and A.news_at(now) is not None:
                    continue
                ev = A.eval_view(now)
                if ev.get("status") in ("passed", "failed", "stuck", "lost", "graduated"):
                    continue
                if A.lit_opposite(dr):
                    continue
                sz = A.size({"risk_pts": float(t["risk"]), "tgt_pts": float(t.get("tgt") or 0.0)}, A.eval_state(now))
                q = int(sz["qty"])
                if q < 1:
                    continue
                st = A.eval_state(now)
                low = min(0.0, float(t.get("w1") or 0.0) * PV * q - COMM * q)
                if st is not None and float(st["room"]) + low <= 0:
                    return {"status": "failed" if not funded else "lost", "sessions": k + 1, "day": d, "pays": pays}
                A.ledger.append({"t": now, "sym": "NQ", "side": "buy" if dr == 1 else "sell", "qty": q, "entry_t": int(t["entry_t"]),
                                 "result": {"ok": True}})
                A.open_t = int(t["entry_t"])
                A.prov[A.open_t] = {"dir": dr, "qty": q}
                a_open, a_today = (t, q), a_today + 1
                n_tr["ATLAS"] += 1
            A.check_lock(now)
            L.check_lock(now)
        if a_open:
            at_, q = a_open
            A._close(int(at_["entry_t"]), int(at_["exit_t"]), round(q * (float(at_["pts"]) * PV - COMM), 2), int(at_["exit_t"]))
            A.open_t = None
        L._busy = 0
        from engine.multi_account import _et  # noqa: F401
        import datetime as _d
        from zoneinfo import ZoneInfo
        clock.t = int(_d.datetime.fromisoformat(d + "T16:30:00").replace(tzinfo=ZoneInfo("America/New_York")).timestamp())
        ev = A.eval_view(clock.t)
        if not funded:
            if ev.get("status") == "passed":
                return {"status": "passed", "sessions": k + 1, "day": d, "balance": ev["balance"], "trades": n_tr}
            if ev.get("status") in ("failed", "stuck"):
                return {"status": ev["status"], "sessions": k + 1, "day": d, "trades": n_tr}
        else:
            fv = A.funded_view(clock.t)
            if ev.get("status") == "lost":
                return {"status": "lost", "sessions": k + 1, "day": d, "pays": pays}
            if fv["ready"]:
                A.spec["funded"]["payouts"][d] = fv["request"]
                pays.append((d, fv["request"]))
                first_pay = first_pay or k + 1
    return {"status": "open" if not funded else "funded", "sessions": len(sessions), "day": sessions[-1], "pays": pays,
            "first_pay_session": first_pay, "trades": n_tr}


def main():
    S, lit, at = trades()
    h2 = [d for d in S if H2[0] <= d <= H2[1]]
    tmp = tempfile.mkdtemp(prefix="rapid_replay_")
    clock = Clock()
    b, L, A = _bot(tmp, {"account": "Sim105", "eval_start": h2[0], "armed": False}, clock)
    out = []
    for i in range(len(h2)):
        r = run_eval(b, L, A, clock, h2[i:], lit, at)
        r["start"] = h2[i]
        out.append(r)
    done = [r for r in out if r["status"] == "passed"]
    fails = [r for r in out if r["status"] in ("failed", "stuck")]
    med = statistics.median([r["sessions"] for r in done]) if done else None
    first = out[0]
    fb, FL_, FA = _bot(os.path.join(tmp, "f"), {"account": "Sim106", "eval_start": h2[0], "stage": "funded",
                                                  "funded_start": h2[0], "payouts": {}}, clock)
    fr = run_eval(fb, FL_, FA, clock, h2, lit, at, funded=True)
    paid = sum(a for _, a in fr.get("pays") or [])
    months = len(h2) / 21.0
    res = {"h2_sessions": len(h2), "starts": len(out), "passed": len(done), "failed_or_stuck": len(fails),
           "unfinished": len(out) - len(done) - len(fails), "median_sessions_to_pass": med,
           "from_jul1": {k: first.get(k) for k in ("status", "sessions", "day", "balance", "trades")},
           "funded_from_jul1": {"status": fr["status"], "payouts": fr.get("pays"), "paid": paid, "to_owner_90pct": round(paid * 0.9, 2),
                                "per_month_to_owner": round(paid * 0.9 / months, 2), "first_payout_session": fr.get("first_pay_session"),
                                "trades": fr.get("trades")}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"result": res, "evals": out}, fh, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
