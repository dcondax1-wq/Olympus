"""LIT on another CME micro (MGC gold, MCL crude, M2K Russell): the full proof in one command. PAPER RESEARCH ONLY: writes
research/other_markets/<SYM>.json, never touches live_model*.json, the live bot or any NQ file. docs/OTHER_MARKETS.md.

Idea (owner 2026-11-18): LIT on markets that do not move with NQ = more winning days on the account, which is what the MFFU
consistency / best-day rules want. ES was rejected before (docs/TESTED_AND_REJECTED.md "E3 same edge, more markets": costs
were 7-13% of R on MES): this re-runs that test per market, with the market's own tick, $ per point, costs and hours.

    python -X utf8 tools/other_markets.py MGC            # imports the NinjaTrader export if new (tools/nt_import.py), then the proof
    python -X utf8 tools/other_markets.py MCL --n 300    # quicker Monte Carlo (default 500 paths)
    python -X utf8 tools/other_markets.py selftest       # the whole chain on a SYNTHETIC export (no real data needed)

What it runs (nothing tuned; engine/lit_markets.py has every pre-registered choice):
  strategy   engine/lit.py run_x with live_model.json "lit" (1m execution, CISD entry, VIX-band target banked at 8R, 15-min
             check, Monday rule, weekly stop), point settings re-scaled by k = the market's median 5m ATR / NQ's on the same
             days, stop 1 tick beyond the sweep extreme, breakeven = costs, the market's commission and 1 tick slippage on
             market fills / stops. Variants (neighbours, NOT a search): stops x0.8 / x1.25; gold / crude also "pit" hours and
             the VIX band instead of their own realized vol. The variant is picked on 2026 Jan-Jun ONLY, checked on Jul-Oct.
  money      the LIT rule size ($800 risk up to a 20-pt NQ-equivalent stop, max 40 micros, weekly stop) through MNQ-equivalent
             points (x $ per point / $2, the commission difference folded in, so $ are exact): trades/week, win %, PF, net $,
             $/month, max drawdown; spans 2026 H1, 2026 H2, 2021-25 when the export reaches back that far
  eval       its own MFFU Builder 50K at the live eval sizing (two_week room_f 0.4 kept to session 80), tools/uprisk.eval_mc:
             pass / fail within 10 sessions (2 weeks), median sessions to pass
  together   daily $ correlation with LIT-NQ (the live ledger, tools/uprisk.trades), and LIT-NQ + LIT-<SYM> on ONE Builder
             50K (same 5-session-block Monte Carlo paths): eval speed, funded first payout, sessions held by the 50% best-day
             (consistency) rule, $ a month, account lost in 6 months, winning days a month
Verdict = the CLAUDE.md bar: both 2026 halves positive with PF > 1 at 2-4 trades a week, 2021-25 positive when present, and
together better than NQ alone on eval AND funded $ in both halves. A pass is a report for the lead / owner, never a switch.
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit_markets as IN  # noqa: E402
from engine import lit  # noqa: E402
from engine.data import _clean_1m, from_frame, load  # noqa: E402
from tools import lit_more as L  # noqa: E402
from tools import nt_import as NI  # noqa: E402
from tools import uprisk as U  # noqa: E402

OUT_DIR = os.path.join(ROOT, "research", "other_markets")
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
USPAN = {"H1": "H1", "H2": "H2", "2021-25": "REF"}            # the matching tools/uprisk spans (NQ ledger to 2026-10-16)
MNQ_PV, MNQ_COMM = 2.0, 1.90
EVAL_VAR = {"room_f": 0.4, "wk_loss_usd": None, "two_week_until": 80}   # live eval switches since 2026-11-14 ("yes 40%")
TPW = (2.0, 4.0)
MIN_SESS, MIN_COVER = 60, 0.8


# ================================================================================================ data
def load_bars(sym: str, data_dir: str):
    """(5m Bars, 1m Bars | None) from <data_dir>/<SYM>_5m.csv / _1m.csv (engine.data rules: junk bars out, true 1m only)."""
    df = pd.read_csv(os.path.join(data_dir, f"{sym}_5m.csv"))
    df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
    b5 = from_frame(sym, "5m", df)
    p1 = os.path.join(data_dir, f"{sym}_1m.csv")
    b1 = None
    if os.path.exists(p1):
        raw = pd.read_csv(p1)[["time", "open", "high", "low", "close", "volume"]]
        clean = _clean_1m(raw, b5)
        if len(clean):
            b1 = from_frame(sym, "1m", clean.drop(columns="bucket"))
    return b5, b1


def _day_atr(b):
    at = lit.atr(b.h, b.l, b.c)
    m = (b.mod >= 120) & (b.mod < 930)
    s = pd.Series(at[m]).groupby(np.asarray(b.date_str)[m]).median()
    return s[s > 0]


def k_ratio(b5) -> dict:
    """k = median 5m ATR(14) (02:00-15:30 ET) of the market / of NQ, over common 2026 Jan-Jun days (else all common days)."""
    ax, an = _day_atr(b5), _day_atr(load("NQ", "5m"))
    com = ax.index.intersection(an.index)
    h1 = [d for d in com if SPANS["H1"][0] <= d <= SPANS["H1"][1]]
    use, how = (h1, "common 2026 Jan-Jun days") if len(h1) >= 40 else ((list(com), "all common days") if len(com) >= 20 else (None, "no common days"))
    if use is None:
        k = float(ax.median() / an.median())
    else:
        k = float(ax.loc[use].median() / an.loc[use].median())
    return {"k": round(k, 6), "how": how, "days": len(use or [])}


def sessions_of(b5) -> list:
    return sorted({d for d, w in zip(b5.date_str, b5.dow) if w < 5})


# ================================================================================================ strategy runs
def run_market(s, b5, b1, k, vol_path, variants=None, log=print) -> dict:
    """variant -> engine trades (research runlib dicts), every variant in its own engine/lit_markets.use block."""
    out = {}
    built = {}
    for v in variants or IN.variants(s):
        band = "VIX" if (v == "vix" or s.vol == "VIX") else s.vol
        with IN.use(s, k, vol_path=vol_path, vol=band):
            if band not in built:
                t0 = time.time()
                M = lit.Market(bars=b5)
                C = lit.candidates(M, ref="cisd")
                B1 = lit.bars_1m(M, src=b1) if b1 is not None else None
                built[band] = (M, C, B1, lit.bars_5m(M))
                log(f"  {s.sym}: {len(C)} LIT setups found ({band} band, {time.time() - t0:.0f}s)")
            M, C, B1, B5 = built[band]
            P = {**L.LIVE, **IN.params(s, k, v)}
            if B1 is None:
                P["tf"] = "5m"
            out[v] = lit.run_x(M, C, P, None, B1=B1 if P["tf"] == "1m" else None, B5=B5)
    return out


def units(T, s) -> list:
    """Engine trades of market s -> per-micro records in MNQ-equivalent points, the commission difference folded in: a q-micro
    trade's $ = pts x $2 x q - $1.90 x q is exactly its own $ (per micro: pnl / q)."""
    x = s.pv / MNQ_PV
    U_ = []
    for t in T:
        q = t["qty"]
        if not q:
            continue
        U_.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": t["dir"], "inst": s.sym,
                   "src": s.sym.lower(), "risk": round(t["risk_pts"] * x, 6), "tgt": round(abs(t["target_px"] - t["entry_px"]) * x, 6),
                   "pts": (t["pnl"] / q + MNQ_COMM) / MNQ_PV, "w1": (t["low"] / q + MNQ_COMM) / MNQ_PV, "exit": t["exit"],
                   "tf": t.get("tf"), "risk_inst": t["risk_pts"]})
    U_.sort(key=lambda u: u["entry_t"])
    return U_


def stats(T, span, sess) -> dict:
    a, z = SPANS[span]
    ss = [d for d in sess if a <= d <= z]
    TT = [t for t in T if a <= t["day"] <= z]
    p = np.array([t["pnl"] for t in TT] or [0.0])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if len(TT) else 0.0
    day = collections.defaultdict(float)
    for t in TT:
        day[t["day"]] += t["pnl"]
    wk = max(1e-9, len(ss) / 5.0)
    return {"sessions": len(ss), "n": len(TT), "tpw": round(len(TT) / wk, 2),
            "win": round(100.0 * sum(1 for t in TT if t["pnl"] > 0) / max(1, len(TT)), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / max(1e-9, len(ss) / 21.0)), "dd": round(dd),
            "worst_day": round(min(day.values())) if day else 0, "best_day": round(max(day.values())) if day else 0}


def cost_share(U_, s) -> float | None:
    """Costs of one micro round trip (commission + 2 ticks: entry and exit slippage) as % of its 1R $ risk."""
    r = [u["risk_inst"] * s.pv for u in U_ if u["risk_inst"] > 0]
    return round(100.0 * float(np.median([(s.comm + 2 * s.tick_usd) / x for x in r])), 1) if r else None


# ================================================================================================ accounts (tools/uprisk)
def by_index(S, U_):
    ix = {d: i for i, d in enumerate(S)}
    BY = [[] for _ in S]
    for u in U_:
        if u["day"] in ix:
            BY[ix[u["day"]]].append({"day": u["day"], "risk": u["risk"], "risk_pts": u["risk"], "tgt": u["tgt"], "tgt_pts": u["tgt"],
                                     "pts": u["pts"], "w1": u["w1"], "size_mult": u.get("wk_m", 1.0), "ref": False})
    return BY


def daily_usd(BY) -> np.ndarray:
    """$ a session at the LIT rule size (weekly-stop half size kept), $1.90 a micro."""
    out = np.zeros(len(BY))
    for i, ts in enumerate(BY):
        for t in ts:
            q = lit.qty_for(t["risk"])
            if q and t.get("size_mult", 1.0) < 1:
                q = max(1, int(q * t["size_mult"] + 1e-9))
            out[i] += t["pts"] * MNQ_PV * q - MNQ_COMM * q
    return out


def covered(S, sess_x, span) -> tuple:
    a, z = U.SPAN[USPAN[span]]
    nq = [d for d in S if a <= d <= z]
    have = set(sess_x)
    n = sum(1 for d in nq if d in have)
    return n, (n / len(nq) if nq else 0.0)


def together(S, BYn, BYx, sess_x, n_mc, log=print) -> dict:
    """NQ alone vs X alone vs NQ + X on one Builder 50K (same paths), per span the export covers."""
    cfg = U.ecfg_of(dict(EVAL_VAR))
    BYc = [a + b for a, b in zip(BYn, BYx)]               # NQ's trade first, then X's (the ledger has no entry minute)
    dn, dx, dc = daily_usd(BYn), daily_usd(BYx), daily_usd(BYc)
    out = {}
    for span in ("H1", "H2", "2021-25"):
        n, cov = covered(S, sess_x, span)
        if n < MIN_SESS or cov < MIN_COVER:
            out[span] = {"skipped": f"export covers {n} of this span's NQ sessions ({cov:.0%})"}
            continue
        a, z = U.span_ix(S, USPAN[span])
        have = np.array([S[i] in set(sess_x) for i in range(a, z)])
        xn, xx = dn[a:z][have], dx[a:z][have]
        both = (xn != 0) & (xx != 0)
        corr = float(np.corrcoef(xn, xx)[0, 1]) if xn.std() > 0 and xx.std() > 0 else None
        corr_b = float(np.corrcoef(xn[both], xx[both])[0, 1]) if both.sum() >= 10 and xn[both].std() > 0 and xx[both].std() > 0 else None
        nql = xn < 0
        months = max(1e-9, have.sum() / 21.0)
        paths = U.mc_paths(S, USPAN[span], n_mc)
        row = {"sessions": int(have.sum()), "corr_daily": None if corr is None else round(corr, 3),
               "corr_both_traded": None if corr_b is None else round(corr_b, 3), "both_traded_days": int(both.sum()),
               "x_won_on_nq_losing_days_pct": round(100.0 * float(((xx > 0) & nql).sum()) / max(1, nql.sum()), 1),
               "win_days_month": {"nq": round(float((xn > 0).sum()) / months, 1),
                                  "nq_plus_x": round(float(((xn + xx) > 0).sum()) / months, 1)}}
        for nm, BY in (("nq", BYn), ("x", BYx), ("nq_plus_x", BYc)):
            e = U.eval_mc(BY, paths, cfg, "builder50k")
            row[nm] = {"eval": {k: e[k] for k in ("p10", "f10", "p_ever", "pass_med", "usd_per_pass")}}
            if nm != "x":
                f = U.funded_mc(BY, paths, "builder50k", U.UP50)
                row[nm]["funded"] = {k: f[k] for k in ("per_month", "first_med", "any_pay", "hold_cons", "loss_6m", "payouts")}
        out[span] = row
        log(f"  together {span}: corr {row['corr_daily']}, eval 2wk pass NQ {row['nq']['eval']['p10']}% -> "
            f"NQ+X {row['nq_plus_x']['eval']['p10']}%, funded $/mo {row['nq']['funded']['per_month']} -> "
            f"{row['nq_plus_x']['funded']['per_month']}")
    return out


# ================================================================================================ the proof
def proof(sym: str, data_dir: str = NI.DATA, n_mc: int = 500, comm: float | None = None, out_dir: str = OUT_DIR, log=print) -> dict:
    s = IN.spec(sym, comm)
    b5, b1 = load_bars(sym, data_dir)
    sess = sessions_of(b5)
    kk = k_ratio(b5)
    k = kk["k"]
    vol_path = os.path.join(data_dir, f"{sym}_rv_1d.csv")
    log(f"{sym}: {len(sess)} sessions {sess[0]} -> {sess[-1]}, 1m bars {'yes' if b1 is not None else 'NO (5m execution)'}, "
        f"k = {k:.4f} ({kk['how']})")
    runs = run_market(s, b5, b1, k, vol_path if os.path.exists(vol_path) else None, log=log)
    res = {"sym": sym, "spec": {**s.__dict__, "tick_usd": s.tick_usd}, "k": kk, "params": {v: IN.params(s, k, v) for v in runs},
           "data": {"first": sess[0], "last": sess[-1], "sessions": len(sess), "has_1m": b1 is not None,
                    "spans": {sp: sum(1 for d in sess if a <= d <= z) for sp, (a, z) in SPANS.items()}},
           "variants": {}, "made": time.strftime("%Y-%m-%d %H:%M")}
    UV = {}
    for v, T in runs.items():
        Uv = L.wk_mults(units(T, s))
        UV[v] = Uv
        MT = L.money_trades(Uv)
        res["variants"][v] = {"cost_pct_of_R": cost_share(Uv, s),
                              **{sp: stats(MT, sp, sess) for sp in SPANS if res["data"]["spans"][sp] >= MIN_SESS}}
    # pick on 2026 H1 only (trades/week in range first), check on H2
    h1 = {v: r["H1"] for v, r in res["variants"].items() if "H1" in r}
    pool = [v for v, r in h1.items() if TPW[0] <= r["tpw"] <= TPW[1]] or list(h1)
    pick = max(pool, key=lambda v: h1[v]["net"]) if pool else "main"
    res["pick"] = pick
    S, BYn = U.load()
    BYx = by_index(S, UV[pick])
    sess_x = [d for d in sess if d in set(S)]
    res["together"] = together(S, BYn, BYx, sess_x, n_mc, log=log)
    for sp in ("H1", "H2", "2021-25"):
        t = res["together"].get(sp, {})
        if "x" in t:
            res["variants"][pick].setdefault(sp, {})["eval_own_50k"] = t["x"]["eval"]
    res["verdict"] = verdict(res)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{sym}.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    log(report(res))
    return res


def verdict(res) -> dict:
    v = res["variants"][res["pick"]]
    why, ok = [], True
    for sp in ("H1", "H2"):
        r = v.get(sp)
        if not r:
            return {"pass": False, "text": f"NOT ENOUGH DATA: the export has no 2026 {sp} (needs both 2026 halves)", "why": []}
        if r["net"] <= 0 or not r["pf"] or r["pf"] <= 1.0:
            ok = False; why.append(f"{sp} loses (net ${r['net']:,}, PF {r['pf']})")
        if not TPW[0] <= r["tpw"] <= TPW[1]:
            ok = False; why.append(f"{sp} {r['tpw']} trades/week (needs 2-4)")
    ref = v.get("2021-25")
    if ref and ref["sessions"] >= 250:
        if ref["net"] <= 0:
            ok = False; why.append(f"2021-25 loses (${ref['net']:,})")
    else:
        why.append("2021-25 not in the export (not checked)")
    tg = res.get("together", {})
    for sp in ("H1", "H2"):
        t = tg.get(sp, {})
        if "nq" not in t:
            ok = False; why.append(f"{sp}: no NQ overlap for the one-account test")
            continue
        en, ec = t["nq"]["eval"], t["nq_plus_x"]["eval"]
        fn, fc = t["nq"]["funded"], t["nq_plus_x"]["funded"]
        if ec["p10"] < en["p10"] or ec["f10"] > en["f10"] + 1.0:
            ok = False; why.append(f"{sp}: NQ+{res['sym']} eval worse (2-week pass {en['p10']}% -> {ec['p10']}%, fail {en['f10']}% -> {ec['f10']}%)")
        if fc["per_month"] <= fn["per_month"]:
            ok = False; why.append(f"{sp}: NQ+{res['sym']} funded $/month not higher ({fn['per_month']} -> {fc['per_month']})")
    txt = (f"PASSES the proof ({res['pick']}): report to the lead / owner, nothing changes live" if ok
           else f"FAILS ({res['pick']}): " + "; ".join(w for w in why if "not checked" not in w))
    return {"pass": ok, "text": txt, "why": why}


def report(res) -> str:
    v = res["variants"][res["pick"]]
    L_ = [f"\n{res['sym']} LIT ({res['pick']}, k {res['k']['k']:.4f}, costs {v.get('cost_pct_of_R')}% of R):",
          f"{'span':8s} {'trades/wk':>9s} {'win%':>5s} {'PF':>5s} {'net $':>9s} {'$/month':>8s} {'max DD':>8s} {'2wk pass/fail':>14s}"]
    for sp in SPANS:
        r = v.get(sp)
        if not r:
            L_.append(f"{sp:8s} not in the export")
            continue
        e = r.get("eval_own_50k") or {}
        L_.append(f"{sp:8s} {r['tpw']:9.2f} {r['win']:5.1f} {str(r['pf']):>5s} {r['net']:9,} {r['per_month']:8,} {r['dd']:8,} "
                  f"{str(e.get('p10', '-')) + '/' + str(e.get('f10', '-')):>14s}")
    for sp, t in res.get("together", {}).items():
        if "nq" in t:
            L_.append(f"together {sp}: corr {t['corr_daily']}, win days/mo {t['win_days_month']['nq']} -> {t['win_days_month']['nq_plus_x']}, "
                      f"funded $/mo {t['nq']['funded']['per_month']} -> {t['nq_plus_x']['funded']['per_month']}, "
                      f"held by 50% rule {t['nq']['funded']['hold_cons']} -> {t['nq_plus_x']['funded']['hold_cons']} sessions")
    L_.append("variants (net $ H1 / H2, picked on H1): " + ", ".join(
        f"{nm} {r.get('H1', {}).get('net', '-')}/{r.get('H2', {}).get('net', '-')}" for nm, r in res["variants"].items()))
    L_.append("VERDICT: " + res["verdict"]["text"])
    return "\n".join(L_)


# ================================================================================================ command line
def ensure_data(sym: str, data_dir: str, log=print) -> bool:
    """Import the NinjaTrader export when it is newer than data/<SYM>_1m.csv (or that file is missing)."""
    ex = NI.find_exports(sym, data_dir)
    p1 = os.path.join(data_dir, f"{sym}_1m.csv")
    if ex and (not os.path.exists(p1) or max(os.path.getmtime(f) for f in ex) > os.path.getmtime(p1)):
        NI.build(sym, ex, data_dir, log=log)
    if not os.path.exists(os.path.join(data_dir, f"{sym}_5m.csv")):
        log(f"No {sym} data yet. In NinjaTrader: Tools > Historical Data > Export, instrument '{sym} ##-##', Last, Minute 1, "
            f"save into the bot's data folder (docs/OTHER_MARKETS.md), then run this again.")
        return False
    return True


def selftest(n_mc: int = 30, log=print) -> dict:
    """The whole chain on a SYNTHETIC MGC export (tests/synth_nt.py) in a temp folder: import, proof, verdict."""
    import shutil
    import tempfile
    from tests import synth_nt as SN
    tmp = tempfile.mkdtemp(prefix="othermk-")
    try:
        b = SN.base_bars("2026-01-02", "2026-10-16", 2400.0, 0.10, seed=11)
        SN.write_nt(b, os.path.join(tmp, "data", "MGC ##-##.Last.txt"), "America/Chicago", 0.10)
        assert ensure_data("MGC", os.path.join(tmp, "data"), log=log)
        return proof("MGC", os.path.join(tmp, "data"), n_mc=n_mc, out_dir=os.path.join(tmp, "out"), log=log)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="LIT on MGC / MCL / M2K: the full proof (paper research only)")
    ap.add_argument("sym", help="MGC | MCL | M2K | selftest")
    ap.add_argument("--n", type=int, default=500, help="Monte Carlo paths (default 500)")
    ap.add_argument("--comm", type=float, help="$ per micro round trip (MFFU's real commission; default: engine/lit_markets.py)")
    ap.add_argument("--data", default=NI.DATA)
    a = ap.parse_args(argv)
    if a.sym.lower() == "selftest":
        selftest(min(a.n, 60))
        return 0
    sym = a.sym.upper()
    if sym not in IN.SPECS or sym == "NQ":
        ap.error("MGC, MCL or M2K")
    if not ensure_data(sym, a.data):
        return 2
    proof(sym, a.data, a.n, a.comm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
