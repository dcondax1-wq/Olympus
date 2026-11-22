"""One-account book (lane E, 2026-11-22): the best COMBINED book of today's strategies on ONE MFFU account.
PAPER RESEARCH ONLY. Design (committed before the scored run): research/onebook/DESIGN.md.
Engine = research/plans/rank.py (real fills), every book on the same paths.

    python -X utf8 research/onebook/book.py [--n 1000]   -> research/onebook/results.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "plans"))
import rank as R  # noqa: E402

RL, SOA, SZ, U = R.RL, R.SOA, R.SZ, R.U
ET = ZoneInfo("America/New_York")
OUT = os.path.join(HERE, "results.json")
ACCTS = ("mffu_builder_50k", "mffu_builder_25k", "mffu_rapid_eod_25k", "mffu_rapid_eod_50k")

# ---------------------------------------------------------------- real fills for ATLAS, keep BLITZ (rapid_patch drops it)
_blitz0 = SOA._blitz
R.AR.rapid_patch(R.AR.T_at(10))
SOA._blitz = _blitz0
SOA._D.clear()
RL._MB.clear()

# ---------------------------------------------------------------- book knobs (set per book; read by the patched sizers)
CFG = {}
PH = {"p": "e"}
_lit_qty, _funded_qty, _q_add = SZ.lit_qty, SZ.funded_qty, RL.q_add


def _scaled(res, m):
    if m == 1.0:
        return res
    res = dict(res)
    res["qty"] = int(math.floor(res["qty"] * m))
    return res


def lit_qty(*a, **k):
    return _scaled(_lit_qty(*a, **k), CFG.get("lit_e", 1.0))


def funded_qty(*a, **k):
    q = _funded_qty(*a, **k)
    m = CFG.get("lit_f", 1.0)
    return q if m == 1.0 else int(math.floor(q * m))


def q_add(t, z, room, cum, maxq, dll):
    s = t["strat"]
    m = CFG.get("add_e" if PH["p"] == "e" else "add_f", 1.0)
    if m <= 0:
        return 0
    b = CFG.get("budget")
    if b:
        if cum <= -b * dll:
            return 0
        dll = b * dll
    if m != 1.0 and isinstance(z.get(s), dict):
        z = {**z, s: {"usd": z[s]["usd"] * m, "f": z[s]["f"] * m}}
    return _q_add(t, z, room, cum, maxq, dll)


SZ.lit_qty, SZ.funded_qty, RL.q_add = lit_qty, funded_qty, q_add
_ev_step, _f_step = RL.Ev.step, R.Funded.step


def ev_step(self, ts, keep=None):
    PH["p"] = "e"
    return _ev_step(self, ts, keep)


def f_step(self, ts, keep=None):
    PH["p"] = "f"
    return _f_step(self, ts, keep)


RL.Ev.step, R.Funded.step = ev_step, f_step


# ---------------------------------------------------------------- trade lists
def _mins(t):
    e = dt.datetime.fromtimestamp(t["entry_t"], ET)
    return e.hour * 60 + e.minute


def filt(BY, keep):
    return [[t for t in ts if keep(t)] for ts in BY]


NY = 9 * 60 + 30
WIN = {
    None: lambda t: True,
    "atlas_ny": lambda t: t["strat"] != "ATLAS" or _mins(t) >= NY,
    "atlas_ldn": lambda t: t["strat"] != "ATLAS" or _mins(t) < NY,
    "strict": lambda t: (_mins(t) < NY) if t["strat"] == "LIT" else (_mins(t) >= NY if t["strat"] == "ATLAS" else True),
}

# name -> (eval mix, funded mix, knobs, window, lane overrides)
LA = ("LIT", "ATLAS")
BOOKS = {
    "B01 LIT only": (("LIT",), ("LIT",), {}, None, {}),
    "B02 ATLAS only": (("ATLAS",), ("ATLAS",), {}, None, {}),
    "B03 LIT + ATLAS first-come": (LA, LA, {}, None, {}),
    "B04 LIT priority budget (ATLAS <= 50% of the day)": (LA, LA, {"budget": 0.5}, None, {}),
    "B05 time split: ATLAS NY only (from 09:30)": (LA, LA, {}, "atlas_ny", {}),
    "B06 time split: ATLAS London only (before 09:30)": (LA, LA, {}, "atlas_ldn", {}),
    "B07 strict windows: LIT before 09:30, ATLAS from 09:30": (LA, LA, {}, "strict", {}),
    "B08 ATLAS x0.5 in the eval, full funded": (LA, LA, {"add_e": 0.5}, None, {}),
    "B09 LIT eval, LIT + ATLAS once funded": (("LIT",), LA, {}, None, {}),
    "B10 size split: LIT x0.75 eval + funded": (LA, LA, {"lit_e": 0.75, "lit_f": 0.75}, None, {}),
    "B11 size split: LIT x0.5 in the eval": (LA, LA, {"lit_e": 0.5}, None, {}),
    "B12 LIT + ATLAS + BLITZ $300": (LA + ("BLITZ",), LA + ("BLITZ",), {}, None, {"BLITZ": 300}),
    "B13 LIT + ATLAS, ATLAS lane x2": (LA, LA, {}, None, {"ATLAS2": True}),
}
EXTRA = {}   # lanes A-D candidates (added at ~06:30 ET if any passed both 2026 halves)


def build(plan, book):
    me, mf, knobs, win, lanes = (BOOKS.get(book) or EXTRA[book])
    sp = R.spec(plan)
    news = plan.startswith("mffu_rapid")
    z = dict(sp["z"])
    if lanes.get("ATLAS2"):
        z["ATLAS"] = {"usd": z["ATLAS"]["usd"] * 2, "f": z["ATLAS"]["f"]}
    if "BLITZ" in lanes:
        z["BLITZ"] = {"usd": float(lanes["BLITZ"]), "f": 0.3}
    sp["z"] = z
    E = sp["E"]
    big = "50k" in plan
    has_cons = E.get("cons", 1.0) < 1.0
    ec = sp["ev"]().cfg
    sp["ev"] = lambda ec=ec, E=E, z=z: RL.Ev(ec, E, z, "guard" if has_cons else "none")
    F, fcfg, ask = sp["F"], (U.UP50 if big else U.UP25), ("cap" if sp["F"]["cap1"] < 1e8 else sp["F"]["pay_min"])
    sp["fund"] = lambda F=F, fcfg=fcfg, z=z, ask=ask: R.Funded(fcfg, F, z, ask)
    k = WIN[win]
    sp["BYe"] = filt(RL.mix_by(me), k)
    sp["BYf"] = filt(RL.mix_by(mf, news=news), k)
    sp["BYx"] = filt(RL.mix_by(mf), k)
    lit_usd = 500.0 if big else 250.0
    usd = {s: 0.0 for s in RL.PRI}
    usd["LIT"] = lit_usd * knobs.get("lit_f", 1.0) if "LIT" in mf else 0.0
    if "ATLAS" in mf:
        usd["ATLAS"] = z["ATLAS"]["usd"]
    if "BLITZ" in mf:
        usd["BLITZ"] = z["BLITZ"]["usd"]
    sp["usd"] = usd
    sp["knobs"] = knobs
    return sp


def run(plan, book, PE, PF, S):
    sp = build(plan, book)
    CFG.clear()
    CFG.update(sp["knobs"])
    row = {}
    for s in R.SPANS:
        row[s] = {"eval": R.eval_run(sp, PE[s]), "slot": R.slot_run(sp, PF[s]),
                  "fixed": SOA.plain_stats(sp["BYx"], S, s, sp["usd"])}
        row[s]["slot"]["per_month"] = round(row[s]["slot"]["net_6m"] / 6.0)
    CFG.clear()
    return row


def today(rows):
    """Today's setup: LIT on a Builder 50K slot + ATLAS alone on a Builder 25K slot, summed (two slots, two fees)."""
    a, b = rows["mffu_builder_50k"]["B01 LIT only"], rows["mffu_builder_25k"]["B02 ATLAS only"]
    out = {}
    for s in R.SPANS:
        A, B = a[s]["slot"], b[s]["slot"]
        out[s] = {"net_6m": A["net_6m"] + B["net_6m"], "per_month": round((A["net_6m"] + B["net_6m"]) / 6.0),
                  "owner_6m": A["owner_6m"] + B["owner_6m"], "fees_6m": round(A["fees_6m"] + B["fees_6m"], 1),
                  "per_dollar": round((A["owner_6m"] + B["owner_6m"]) / (A["fees_6m"] + B["fees_6m"]), 2),
                  "first_pay_med_50k": A["first_pay_med"], "first_pay_med_25k": B["first_pay_med"],
                  "tpw": round(a[s]["fixed"]["tpw"] + b[s]["fixed"]["tpw"], 1)}
    return out


def pick(rows, T):
    cands = []
    for plan, books in rows.items():
        bar = books["B01 LIT only"]["H1"]["eval"]["fail"] + 2.0
        for bk, r in books.items():
            if r["H1"]["eval"]["fail"] <= bar:
                cands.append((r["H1"]["slot"]["net_6m"], plan, bk))
    cands.sort(reverse=True)
    _, plan, bk = cands[0]
    r = rows[plan][bk]
    chk = {"H1_beats_today": r["H1"]["slot"]["net_6m"] > T["H1"]["net_6m"],
           "H2_beats_today": r["H2"]["slot"]["net_6m"] > T["H2"]["net_6m"],
           "REF_not_worse": r["REF"]["slot"]["net_6m"] >= T["REF"]["net_6m"]}
    chk["card"] = all(chk.values())
    return {"plan": plan, "book": bk, "eligible": len(cands), "top5_h1": cands[:5], **chk}


def line(plan, bk, r):
    return f"{plan:20s} {bk:56s} " + " | ".join(
        f"{s} ${r[s]['slot']['per_month']}/mo pass {r[s]['eval']['pass']}/{r[s]['eval']['fail']}% ~{r[s]['eval']['med_days']}d "
        f"1st {r[s]['slot']['first_pay_med']} x{r[s]['slot']['per_dollar']} {r[s]['fixed']['tpw']}/wk PF {r[s]['fixed']['pf']}"
        for s in R.SPANS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    t0 = time.time()
    S = SOA.data()["S"]
    PF = {s: U.mc_paths(S, s, a.n, length=R.LEN, seed=23) for s in R.SPANS}
    PE = {s: U.mc_paths(S, s, a.n, length=R.H_EVAL, seed=7) for s in R.SPANS}
    rows = {}
    for plan in ACCTS:
        rows[plan] = {}
        for bk in list(BOOKS) + list(EXTRA):
            if a.only and a.only not in bk:
                continue
            rows[plan][bk] = run(plan, bk, PE, PF, S)
            print(line(plan, bk, rows[plan][bk]), f"[{time.time() - t0:.0f}s]", flush=True)
    out = {"n": a.n, "books_counted": sum(len(v) for v in rows.values()) + 1, "rows": rows}
    if not a.only:
        out["today"] = today(rows)
        out["pick"] = pick(rows, out["today"])
        print("TODAY", out["today"])
        print("PICK", out["pick"])
    with open(OUT if not a.only else OUT.replace(".json", "_partial.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
