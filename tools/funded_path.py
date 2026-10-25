"""The funded money plan (2026-10-25, research/writeups/funded-path.md): the eval -> MFFU Builder Sim Funded -> payout path
replayed on the 2026 trades for both bots, through the funded tracker (engine/funded_life.track) and the funded sizing
(engine/sizing.funded_qty, the research rule of lit-funded-sizing.md, with and without the consistency-aware cap).

Trades (futures only, costs in at $1.90 a micro round trip, 1 tick of slippage on market entries / stop exits already in
the prices):
  LIT    the 120 trades of run lit_live (research/handoff/2026-10-25/COMPLETE_TRADE_LEDGER.csv rows T-2026-*): stop
         distance, target distance, points, worst open (mae_r x stop), weekly-stop half size (ledger micros < the LIT rule)
  ATLAS  the 2026 trades of book ALONE_USD500 (research/handoff/2026-10-25/ATLAS_TRADE_LEDGER.csv)
Sessions: CME NQ1! daily bars (data/NQ_1d.csv), 2026-01-02 .. 2026-10-16. H1 = Jan-Jun (pick), H2 = Jul-Oct (check).
Each funded account: 126 sessions (6 months); Monte Carlo 1,000 paths in 5-session blocks from the half (seed 23), plus the
real path from the half's first session. A payout is requested at a session's end when engine/funded_life.track says
"ready" (all MFFU rules met AND the owner's habit: $1,500 / $750 above the buffer), for the max it allows.

  python tools/funded_path.py          -> research/lit/funded_path.json + the run files (tools/runlib, research/runs/)
Paper only.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import funded_life as FL  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = 2.0, 1.90, 0.25
HO = os.path.join(ROOT, "research", "handoff", "2026-10-25")
OUT = os.path.join(ROOT, "research", "lit", "funded_path.json")
N_MC, BLOCK, LEN = 1000, 5, 126
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16")}

# the research rule (lit-funded-sizing.md; engine/multi_account PRESETS funded blocks)
CFG_50 = {"pct": 0.4, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "wk": True, "room_f": None, "max_win": 1500,
          "slip_ticks": 2, "skip_breach": True}
CFG_25 = {"pct": 0.4, "pct_min_usd": 50, "pct_max_usd": 400, "ref": 20, "wk": True, "room_f": None, "max_win": 750,
          "slip_ticks": 2, "skip_breach": True}


def sessions():
    out = []
    with open(os.path.join(ROOT, "data", "NQ_1d.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            d = dt.datetime.fromtimestamp(int(float(r["time"])), dt.timezone.utc).date()
            if "2026-01-01" <= d.isoformat() <= "2026-10-16" and d.weekday() < 5:
                out.append(d.isoformat())
    return sorted(set(out))


def lit_trades():
    by = {}
    with open(os.path.join(HO, "COMPLETE_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r["trade_id"].startswith("T-2026"):
                continue
            d = 1 if r["direction"] == "long" else -1
            e, s, tg, x = (float(r[k]) for k in ("entry_price", "initial_stop", "target_price", "exit_price"))
            risk = abs(e - s)
            base = qty_for(risk)
            wk = 0.5 if base and int(r["quantity"]) < base else 1.0
            day = r["entry_fill_at"][:10]
            by.setdefault(day, []).append({"day": day, "risk": risk, "risk_pts": risk, "tgt": abs(tg - e), "tgt_pts": abs(tg - e),
                                           "pts": (x - e) * d, "w1": -float(r["mae_r"] or 0) * risk, "size_mult": wk})
    return by


def atlas_trades():
    by = {}
    with open(os.path.join(HO, "ATLAS_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["day"] < "2026" or r["book"] != "ALONE_USD500":
                continue
            d = int(r["dir"])
            e, tg, x = float(r["entry_px"]), float(r["target_px"]), float(r["exit_px"])
            risk = float(r["risk_pts"])
            by.setdefault(r["day"], []).append({"day": r["day"], "risk": risk, "risk_pts": risk, "tgt": abs(tg - e),
                                                "tgt_pts": abs(tg - e), "pts": (x - e) * d,
                                                "w1": -float(r["mae"] or 0) * risk, "size_mult": 1.0})
    return by


def acct_of(plan: str) -> dict:
    P = FL.plan_of(plan)
    return {"mll": P["mll"], "lock": P["lock"], "dll": P["dll"], "buffer": P["buffer"], "pay_min": P["pay_min"],
            "pay_max": P["pay_max"], "split": P["split"], "cons": P["cons"], "cycle_days": P["cycle_days"],
            "max_payouts": P["max_payouts"], "max_micros": P["max_micros"], "scale": 1.0}


_CAL = []


def cal(k: int) -> str:
    """Synthetic calendar for a path (block resampling repeats days): weekday k from 2027-01-04."""
    while len(_CAL) <= k:
        d = dt.date(2027, 1, 4) if not _CAL else dt.date.fromisoformat(_CAL[-1]) + dt.timedelta(days=1)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        _CAL.append(d.isoformat())
    return _CAL[k]


def _rec(t, q, pnl):
    """A sized trade in the run library's columns (tools/runlib.TRADE_COLS); day = the real 2026 session."""
    d = dt.date.fromisoformat(t["day"])
    et = int(dt.datetime(d.year, d.month, d.day, 14, 0, tzinfo=dt.timezone.utc).timestamp()) + len(_REC_SEEN)
    _REC_SEEN.append(1)
    ru = t["risk"] * PV * q
    return {"day": t["day"], "entry_t": et, "exit_t": et + 60, "dir": 1, "r": round(pnl / ru, 3) if ru else 0.0, "pnl": round(pnl, 2),
            "risk_pts": t["risk"], "qty": q, "risk_usd": round(ru, 2), "half": t.get("size_mult", 1.0) < 1, "exit": "",
            "trigger": "funded", "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None}


_REC_SEEN = []


def run(by_sess: list, seq: list, plan: str, cfg: dict, keep=None) -> dict:
    """One funded account over the session indices seq. by_sess[i] = that session's trades."""
    A = acct_of(plan)
    P = FL.plan_of(plan)
    days, pays = {}, {}
    pay_at, cons_block, max_risk = [], 0, 0.0
    first = None
    for k, si in enumerate(seq):
        day = cal(k)
        prev = dict(days)
        st0 = SZ.funded_state(prev, 0.0, pays, plan=A)
        cyc = SZ.funded_cycle(prev, 0.0, pays, plan=A)
        if pays:
            st0["floor"] = max(st0["floor"], A["lock"])
        cum = 0.0
        for t in by_sess[si]:
            if cum <= -A["dll"]:
                break
            room = round(st0["balance"] + cum - st0["floor"], 2)
            st = {"room": room, "cum": cum, "locked": st0["floor"] >= A["lock"] - 1e-9, **cyc}
            q = SZ.funded_qty(t, st, cfg, acct=A)
            if q <= 0:
                continue
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            max_risk = max(max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -A["dll"]:
                pnl = -A["dll"] - cum - SLIP * PV * q
                low = pnl
            if st0["balance"] + cum + low <= st0["floor"]:
                days[day] = round(cum + (st0["floor"] - st0["balance"] - cum), 2)
                if keep is not None:
                    keep.append(_rec(t, q, st0["floor"] - st0["balance"] - cum))
                return {"lost": k + 1, "pay_at": pay_at, "first": first, "cons_block": cons_block, "grad": None, "max_risk": max_risk}
            cum += pnl
            if keep is not None:
                keep.append(_rec(t, q, pnl))
        if abs(cum) > 1e-9:
            days[day] = round(cum, 2)
        tr = FL.track(days, pays, P, today=day)
        if tr["status"] == "consistency" and tr["above_buffer"] >= P["ask_above"]:
            cons_block += 1                    # money is there, only the 50% rule holds it back today
        if tr["status"] == "ready":
            amt = tr["max_request"]
            pays[day] = amt
            pay_at.append((k + 1, amt * P["split"]))
            first = first or k + 1
            if len(pays) >= P["max_payouts"]:
                return {"lost": None, "pay_at": pay_at, "first": first, "cons_block": cons_block, "grad": k + 1, "max_risk": max_risk}
    return {"lost": None, "pay_at": pay_at, "first": first, "cons_block": cons_block, "grad": None, "max_risk": max_risk}


def span_ix(S, span):
    a, z = SPAN[span]
    ix = [i for i, d in enumerate(S) if a <= d <= z]
    return ix[0], ix[-1] + 1


def mc(by_sess, S, span, plan, cfg, n=N_MC):
    a, z = span_ix(S, span)
    rng = np.random.default_rng(23)
    R = []
    for _ in range(n):
        s = []
        while len(s) < LEN:
            b = int(rng.integers(a, z - BLOCK + 1))
            s.extend(range(b, b + BLOCK))
        R.append(run(by_sess, s[:LEN], plan, cfg))
    o = {"paths": n}
    for lab, h in (("3m", 63), ("6m", 126)):
        paid = [sum(x for k, x in r["pay_at"] if k <= h) for r in R]
        o[f"loss_{lab}"] = round(100.0 * sum(1 for r in R if r["lost"] and r["lost"] <= h) / n, 1)
        o[f"paid_{lab}"] = round(float(np.mean(paid)))
        o[f"paid_p10_{lab}"] = round(float(np.percentile(paid, 10)))
        o[f"any_pay_{lab}"] = round(100.0 * sum(1 for r in R if r["first"] and r["first"] <= h) / n, 1)
    o["per_month"] = round(o["paid_6m"] / 6.0)
    fr = [r["first"] for r in R if r["first"]]
    o["first_med"] = float(np.median(fr)) if fr else None
    o["first_p75"] = float(np.percentile(fr, 75)) if fr else None
    o["payouts_mean"] = round(float(np.mean([len(r["pay_at"]) for r in R])), 2)
    o["grad_6m"] = round(100.0 * sum(1 for r in R if r["grad"]) / n, 1)
    o["cons_block_days"] = round(float(np.mean([r["cons_block"] for r in R])), 1)
    o["cons_block_any"] = round(100.0 * sum(1 for r in R if r["cons_block"]) / n, 1)
    o["max_risk"] = round(max(r["max_risk"] for r in R))
    return o


def real(by_sess, S, span, plan, cfg):
    a, z = span_ix(S, span)
    keep = []
    r = run(by_sess, list(range(a, z)), plan, cfg, keep=keep)
    return {"sessions": z - a, "first": r["first"], "payouts": len(r["pay_at"]), "paid": round(sum(x for _, x in r["pay_at"])),
            "lost": r["lost"], "cons_block_days": r["cons_block"], "pay_at": [[k, round(x)] for k, x in r["pay_at"]]}, keep


CONFIGS = [
    ("lit50_rec", "LIT on the Builder 50K: research rule (40% room, <= $800, winner <= $1,500)", "lit", "builder50k", CFG_50),
    ("lit50_cons", "LIT 50K: research rule + consistency-aware cap", "lit", "builder50k", {**CFG_50, "cons_aware": True}),
    ("lit50_cons2", "LIT 50K: research rule + consistency-aware cap after the 1st payout", "lit", "builder50k",
     {**CFG_50, "cons_aware": "after_payout"}),
    ("atlas25_rec", "ATLAS on the Builder 25K: 25K funded rule (40% room, <= $400, winner <= $750)", "atlas", "builder25k", CFG_25),
    ("atlas25_cons", "ATLAS 25K: 25K rule + consistency-aware cap", "atlas", "builder25k", {**CFG_25, "cons_aware": True}),
    ("atlas25_cons2", "ATLAS 25K: 25K rule + consistency-aware cap after the 1st payout", "atlas", "builder25k",
     {**CFG_25, "cons_aware": "after_payout"}),
    ("lit25_rec", "LIT on a Builder 25K (the 3rd account): 25K funded rule", "lit", "builder25k", CFG_25),
    ("lit25_cons", "LIT 25K: 25K rule + consistency-aware cap", "lit", "builder25k", {**CFG_25, "cons_aware": True}),
]


def main():
    S = sessions()
    T = {"lit": lit_trades(), "atlas": atlas_trades()}
    BY = {k: [v.get(d, []) for d in S] for k, v in T.items()}
    out = {"built": dt.date.today().isoformat(), "sessions": len(S), "first": S[0], "last": S[-1],
           "trades": {k: sum(len(x) for x in v.values()) for k, v in T.items()}, "configs": {}}
    for cid, title, strat, plan, cfg in CONFIGS:
        row = {"title": title, "strategy": strat, "plan": plan, "cfg": cfg}
        for sp in ("H1", "H2"):
            row[sp] = mc(BY[strat], S, sp, plan, cfg)
            row[sp + "_real"], _ = real(BY[strat], S, sp, plan, cfg)
        out["configs"][cid] = row
        h1, h2 = row["H1"], row["H2"]
        print(f"{cid:13s} H1 ${h1['per_month']:>5}/mo lost {h1['loss_6m']:>4}% first {h1['first_med']} cons-block {h1['cons_block_days']}d "
              f"| H2 ${h2['per_month']:>5}/mo lost {h2['loss_6m']:>4}% first {h2['first_med']} cons-block {h2['cons_block_days']}d "
              f"| real H1 {row['H1_real']['payouts']} pays ${row['H1_real']['paid']} first {row['H1_real']['first']} "
              f"· H2 {row['H2_real']['payouts']} pays ${row['H2_real']['paid']} first {row['H2_real']['first']}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)
    if "--no-save" not in sys.argv:
        save(out, BY, S)
    return out


ADOPT = {"lit50_rec", "atlas25_rec", "lit25_rec"}


def save(out, BY, S):
    """rl.save one run per config (research/runs/funded_path_<id>.json): the stored trades are the real H1 and H2 funded
    paths (state-dependent size); the funded numbers (MC payouts, loss, first payout, consistency blocks) are in the verdict
    and research/lit/funded_path.json."""
    from tools import runlib as rl
    for cid, title, strat, plan, cfg in CONFIGS:
        r = out["configs"][cid]
        T = []
        for sp in ("H1", "H2"):
            real(BY[strat], S, sp, plan, cfg)
            a, z = span_ix(S, sp)
            run(BY[strat], list(range(a, z)), plan, cfg, keep=T)
        T.sort(key=lambda t: (t["day"], t["entry_t"]))
        h1, h2 = r["H1"], r["H2"]
        verdict = (f"{title}. MC 1,000 x 6 months, H1 / H2: paid to you ${h1['paid_6m']:,} / ${h2['paid_6m']:,} "
                   f"(${h1['per_month']:,} / ${h2['per_month']:,} a month), account lost {h1['loss_6m']}% / {h2['loss_6m']}%, median "
                   f"first payout session {h1['first_med']} / {h2['first_med']}, payouts {h1['payouts_mean']} / {h2['payouts_mean']}, "
                   f"days the money was there but the 50% rule held it {h1['cons_block_days']} / {h2['cons_block_days']}. Real path "
                   f"H1 {r['H1_real']['payouts']} payouts ${r['H1_real']['paid']:,} (first session {r['H1_real']['first']}), H2 "
                   f"{r['H2_real']['payouts']} payouts ${r['H2_real']['paid']:,} (first {r['H2_real']['first']}).")
        rl.save("funded_path_" + cid, title, "risk", "Once an eval passes: what does the MFFU Builder Sim Funded account pay, "
                "how fast, and does a consistency-aware size help?", params={"plan": plan, "strategy": strat},
                sizing={"mode": "funded", **cfg}, trades=T, scored=rl.score(T, S), status="adopt-candidate" if cid in ADOPT else "rejected",
                verdict=verdict, notes=("tools/funded_path.py; tracker engine/funded_life.track, sizing engine/sizing.funded_qty; "
                                        "payout when every MFFU rule is met and $1,500 (50K) / $750 (25K) sits above the buffer; "
                                        "$1.90 a micro. Run-library eval columns are not the funded numbers (see the verdict)."),
                writeup="funded-path", tags=["funded", strat, plan])
        print("saved funded_path_" + cid, flush=True)


if __name__ == "__main__":
    main()
