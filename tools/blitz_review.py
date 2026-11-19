"""BLITZ review (2026-11-18 night, owner: "I expect all of our strategies to be better", "high win rate / profit").
Research only: nothing here is imported by the engine and no live file is touched. research/writeups/blitz-review-2026-11-18.md.

  1. measure today's rule honestly (engine/blitz.py VERSION 2 as account C = never opposite Zlarior / ATLAS, closed first at
     their opposite entry): $150 a trade (at least 1 micro), $1.90 a micro round trip + 1 tick on every market / stop fill
     (entry +1 tick, exit -1 tick), plus a stress with one MORE tick each way; trades / week, win %, PF, net, $ / month, max DD,
     by check time, side, first / later band break, exit kind, VIX tercile, year (2021-25), and the 25K eval at the live size
     (40% of the room, the full room from session 5, the later-break size x0.5 / x1.75)
  2. why losers lose / winners win, BLITZ-only facts the anatomy night (win-loss-anatomy-2026-11-18.md) did not show: where
     the R goes by exit kind, the first 10 minutes (best point by minute 10 vs the final R), giveback of the winners
  3. the 8 pre-declared exit ideas (IDEAS, written before the first run): an early no-follow-through cut (the anatomy: 72% of
     BLITZ's lost $ never reached +0.5R), a back-inside-the-noise-band exit, breakeven at +0.5R, a longer hold for the
     trades that survive the cut. Pick on 2026 Jan-Jun ($ a month at $150), check on Jul-Oct and 2021-25, costs in, still a
     scalper (>= 5 trades a week), 25K eval 2-week fails not up, daily sign-flip placebo per half.
The executor (sim) replays tools/blitz25k_lib._sim for today's rule trade for trade (checked in `run`: 0 differences) and
adds the new exits. One timeframe per process (memory): 2026 on 1m, 2021-25 on 5m (the same rule; 2026 on 5m is shown too).

    /home/user/heavy.sh python -X utf8 tools/blitz_review.py run --tf 1     # -> research/scalp/blitz_review_tf1.json
    /home/user/heavy.sh python -X utf8 tools/blitz_review.py run --tf 5     # -> research/scalp/blitz_review_tf5.json
    python -X utf8 tools/blitz_review.py merge                             # -> research/scalp/blitz_review.json (verdict)
    python -X utf8 tools/blitz_review.py register                          # ZEUS Lab rows (kind blitz_idea)
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import subprocess
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

OUT_DIR = os.path.join(ROOT, "research", "scalp")
OUT = os.path.join(OUT_DIR, "blitz_review.json")
DATE = "2026-11-18"
USD = 150.0
TICK, PV, COMM = 0.25, 2.0, 1.90
EZ = {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0), "later": True}     # account C's live 25K eval size
FZ = {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}                    # account C's funded 25K size
TODAY = {"hold": 30, "chk": None, "band": None, "be": None}
# written down before the first run (2026-11-18 night); "chk" = (minute, best point under x R, only when in a loss)
IDEAS = {
    "chk10_loss": {"chk": (10, 0.5, True), "title": "out at minute 10 if in a loss and never +0.5R"},
    "chk15_loss": {"chk": (15, 0.5, True), "title": "out at minute 15 if in a loss and never +0.5R"},
    "chk10_any": {"chk": (10, 0.25, False), "title": "out at minute 10 if never +0.25R"},
    "band_in": {"band": 0, "title": "out on a 1m close back inside the noise band"},
    "band_in10": {"band": 10, "title": "out on a close back inside the band, from minute 10"},
    "be05": {"be": 0.5, "title": "stop to breakeven at +0.5R"},
    "chk15_loss_h45": {"chk": (15, 0.5, True), "hold": 45, "title": "minute-15 cut, survivors held 45 minutes"},
    "band_in10_h45": {"band": 10, "hold": 45, "title": "back-inside-the-band exit from minute 10, held 45 minutes"},
}
SPANS_TF = {1: ("H1", "H2"), 5: ("R", "H1", "H2", "2022", "2023", "2024", "2025")}
NAMES = {"H1": "2026 Jan-Jun", "H2": "2026 Jul-Oct", "R": "2021-25", "2022": "2022", "2023": "2023", "2024": "2024", "2025": "2025"}


def _ledger():
    """tools/scalp_na_lib reads the LIT ledger from research/handoff (not in every checkout): extract it from git if missing."""
    from tools import runlib as rl
    if not getattr(rl.load, "_git", False):           # a sparse checkout without research/runs/: read a run from git
        _load = rl.load

        def load(id):
            if os.path.exists(os.path.join(rl.RUNS, id + ".json")):
                return _load(id)
            return json.loads(subprocess.run(["git", "-C", ROOT, "show", f"HEAD:research/runs/{id}.json"], capture_output=True,
                                             check=True).stdout)
        load._git = True
        rl.load = load
    from tools import scalp_na_lib as N
    if os.path.exists(N.LEDGER):
        return
    alt = os.path.join(ROOT, "research", "runs", "_cache", "COMPLETE_TRADE_LEDGER_2026-10-25.csv")
    if not os.path.exists(alt):
        os.makedirs(os.path.dirname(alt), exist_ok=True)
        blob = subprocess.run(["git", "-C", ROOT, "show", "HEAD:research/handoff/2026-10-25/COMPLETE_TRADE_LEDGER.csv"],
                              capture_output=True, check=True).stdout
        with open(alt, "wb") as fh:
            fh.write(blob)
    N.LEDGER = alt


def _spans(B, sp):
    from tools import scalp_mo_lib as L
    from tools import scalp_na_lib as N
    if sp.isdigit():
        L.SPANS.setdefault(sp, (f"{sp}-01-01", f"{sp}-12-31"))
    return N.sessions(B, sp)


# ================================================================================================ the executor
def inputs(B, cmode="lit+atlas"):
    from tools import blitz25k_lib as K
    G = K.base(B)
    I, D = G["sig"].astype(np.int64), G["dir"].astype(np.float64)
    F0 = K._signals_win(B, "rth")
    AC = K.account_c(B, cmode)
    brk = np.zeros(len(I))
    seen = collections.Counter()
    for q in range(len(I)):
        seen[(int(B["day"][I[q]]), D[q])] += 1
        brk[q] = seen[(int(B["day"][I[q]]), D[q])]
    return {"sig": I, "dir": D, "stop": B["c"][I] - D * 1.5 * B["atr5"][I], "up": F0["_up"], "lo": F0["_lo"], "ac": AC, "brk": brk}


def sim(B, X, v=None):
    """Today's rule (= blitz25k_lib._sim with the ATR stop, no target, account C) + the new exits of v."""
    v = {**TODAY, **(v or {})}
    o, h, l, c, t = B["o"], B["h"], B["l"], B["c"], B["t"]
    flat, day, mod, tf = B["flat"], B["day"], B["mod"], B["tf"]
    up, lo = X["up"], X["lo"]
    use_c = X["ac"] is not None
    hl, hs, cl, cs = X["ac"] if use_c else (None,) * 4
    hold = max(1, int(round(v["hold"] / tf)))
    chk = v["chk"]
    ck_i = max(1, int(round(chk[0] / tf))) - 1 if chk else -1
    band = v["band"]
    band_i = max(0, int(round(band / tf)) - 1) if band is not None else None
    out = []
    busy, cur, dn, dR = -1, -1, 0, 0.0
    for q in range(len(X["sig"])):
        s = int(X["sig"][q])
        d = int(day[s])
        if d != cur:
            cur, dn, dR = d, 0, 0.0
        if s < busy or dn >= 6 or dR <= -3.0:
            continue
        fe = int(flat[s])
        if s + 1 > fe or mod[s] > 930:
            continue
        D = float(X["dir"][q])
        j = s + 1
        if use_c and ((D > 0 and hs[j]) or (D < 0 and hl[j])):
            continue
        st = float(X["stop"][q])
        fill = o[j] + D * TICK
        risk = D * (fill - st)
        if risk < TICK:
            busy = j
            continue
        stp, ext, mae, mfe10 = st, fill, 0.0, None
        xk, xp, kind = -1, 0.0, ""
        dl = j + hold
        for i in range(j, fe + 1):
            first = i == j
            if not first and use_c and ((D > 0 and cs[i]) or (D < 0 and cl[i])):
                xp, xk, kind = o[i] - D * TICK, i, "hedge"
                mae = max(mae, D * (fill - xp))
                break
            if not first and ((D > 0 and o[i] <= stp) or (D < 0 and o[i] >= stp)):
                xp, xk, kind = o[i] - D * TICK, i, "stop"
                mae = max(mae, D * (fill - xp))
                break
            adv = (fill - l[i]) if D > 0 else (h[i] - fill)
            if (D > 0 and l[i] <= stp) or (D < 0 and h[i] >= stp):
                xp, xk, kind = stp - D * TICK, i, "stop"
                mae = max(mae, D * (fill - xp))
                break
            mae = max(mae, adv)
            if i >= fe:
                xp, xk, kind = c[i] - D * TICK, i, "flat"
                break
            if i >= dl:
                xp, xk, kind = c[i] - D * TICK, i, "time"
                break
            best = max(ext, h[i]) if D > 0 else min(ext, l[i])
            k_in = i - j
            if k_in == max(0, int(round(10 / tf)) - 1):
                mfe10 = D * (best - fill)
            if chk and k_in == ck_i and D * (best - fill) < chk[1] * risk and (not chk[2] or D * (c[i] - fill) < 0):
                xp, xk, kind = c[i] - D * TICK, i, "check"
                break
            if band_i is not None and k_in >= band_i and ((D > 0 and c[i] < up[i]) or (D < 0 and c[i] > lo[i])):
                xp, xk, kind = c[i] - D * TICK, i, "band"
                break
            ext = best
            mf = D * (ext - fill)
            if v["be"] and mf >= v["be"] * risk:
                nb = fill + D * 0.25
                if D * (nb - stp) > 0:
                    stp = nb
            if mf >= 1.0 * risk:
                nt = ext - D * 1.5 * risk
                if D * (nt - stp) > 0:
                    stp = nt
        pts = D * (xp - fill)
        if kind == "stop" and pts > 0:
            kind = "trail"
        out.append({"day": B["dates"][day[j]], "sig_t": int(t[s]), "entry_t": int(t[j]), "exit_t": int(t[xk]) + 60 * tf, "dir": int(D),
                    "entry": float(fill), "stop": st, "exit": float(xp), "exit_kind": kind, "pts": round(pts, 4), "risk_pts": round(risk, 4),
                    "mae_pts": round(mae, 4), "mfe_pts": round(D * (ext - fill), 4), "mfe10": mfe10, "bars": xk - j + 1,
                    "pnl_pm": pts * PV - COMM, "risk_pm": (risk + TICK) * PV + COMM, "mae_pm": -mae * PV - COMM, "kind": 0,
                    "check": int(mod[s] + tf), "brk": int(X["brk"][q]), "lb": 0.5 if X["brk"][q] < 2 else 1.75})
        busy = xk
        dn += 1
        dR += (pts * 2.0 - 1.9) / ((risk + TICK) * 2.0 + 1.9)
    return out


# ================================================================================================ scoring
def qty_lb(t, room, cum, bal, P, sz):
    """scalp_na_lib.qty + the later-break eval size (engine/account_c: x0.5 first break, x1.75 later, never past the room)."""
    from tools import blitz25k_lib as K
    m = float(t.get("lb", 1.0)) if sz.get("later") else 1.0
    z = dict(sz)
    if m != 1.0:
        z["f"] = min(float(z["f"]) * m, 1.0)
        z["cap"] = float(z["cap"]) * m
    return K._NQTY(t, room, cum, bal, P, z)          # scalp_na_lib's own qty (blitz25k_size routes N.qty elsewhere)


def q150(t):
    return max(1, min(20, int(USD / t["risk_pm"])))


def fixed(T, S, extra_ticks=0):
    from tools import scalp_na_lib as N
    from tools import blitz25k_lib as K
    if extra_ticks:
        T = [{**t, "pnl_pm": t["pnl_pm"] - 2 * extra_ticks * TICK * PV} for t in T]
    o = N.stats(T, S, USD, 20)
    o["wk2"] = K.wk2(N.span_trades(T, S), S)
    return o


def group(T, key):
    """$ at $150 a trade by a key: n, win %, avg R, PF, net."""
    G = collections.defaultdict(list)
    for t in T:
        G[key(t)].append(t)
    out = {}
    for k in sorted(G):
        p = np.array([q150(t) * t["pnl_pm"] for t in G[k]])
        R = np.array([t["pnl_pm"] / t["risk_pm"] for t in G[k]])
        gl = -p[p < 0].sum()
        out[str(k)] = {"n": len(p), "win": round(100.0 * float((p > 0).mean()), 1), "avg_r": round(float(R.mean()), 3),
                       "pf": round(float(p[p > 0].sum() / gl), 2) if gl else 99.0, "net": round(float(p.sum()))}
    return out


def anatomy(T):
    """BLITZ-only path facts: exit kinds, the first 10 minutes, winners' giveback."""
    R = lambda t: t["pnl_pm"] / t["risk_pm"]  # noqa: E731
    o = {"exit": group(T, lambda t: t["exit_kind"])}
    m10 = [t for t in T if t.get("mfe10") is not None]
    cut = lambda t: "best by min 10 < 0.5R" if t["mfe10"] < 0.5 * t["risk_pts"] else "best by min 10 >= 0.5R"  # noqa: E731
    o["first10"] = group(m10, cut)
    W = [t for t in T if t["pnl_pm"] > 0]
    if W:
        give = [(t["mfe_pts"] - t["pts"]) / t["risk_pts"] for t in W]
        o["winners"] = {"n": len(W), "median_best_r": round(float(np.median([t["mfe_pts"] / t["risk_pts"] for t in W])), 2),
                        "median_kept_r": round(float(np.median([R(t) for t in W])), 2), "median_giveback_r": round(float(np.median(give)), 2)}
    Lz = [t for t in T if t["pnl_pm"] <= 0]
    if Lz:
        never = [t for t in Lz if t["mfe_pts"] < 0.5 * t["risk_pts"]]
        o["losers"] = {"n": len(Lz), "lost": round(float(sum(q150(t) * t["pnl_pm"] for t in Lz))),
                       "never_05r_share_of_lost": round(100.0 * sum(q150(t) * t["pnl_pm"] for t in never) /
                                                       min(-1e-9, sum(q150(t) * t["pnl_pm"] for t in Lz)), 1),
                       "full_stop_share": round(100.0 * sum(1 for t in Lz if t["exit_kind"] == "stop") / len(Lz), 1),
                       "median_r": round(float(np.median([R(t) for t in Lz])), 2)}
    return o


def daily(T):
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += q150(t) * t["pnl_pm"]
    return by


def flip_p(T, T0, S):
    from tools import zeus_lab as Z
    a, b = daily(N_span(T, S)), daily(N_span(T0, S))
    d = [a.get(k, 0.0) - b.get(k, 0.0) for k in sorted(set(a) | set(b))]
    return Z.signflip_p([x for x in d if abs(x) > 1e-6], 4000), [round(x, 2) for x in d if abs(x) > 1e-6]


def N_span(T, S):
    return [t for t in T if S and S[0] <= t["day"] <= S[-1]]


def vix_terc(T, cuts):
    from tools import scalp_na_lib as N
    def k(t):
        v = N.prev_close("VIX", t["day"])
        return "low" if v < cuts[0] else ("mid" if v < cuts[1] else "high")
    return group(T, k)


def eval_line(T, S, life=False):
    from tools import blitz25k_lib as K
    from tools import blitz25k_size as BS
    old = K.qty
    K.qty = qty_lb
    try:
        e = BS.eval_score(T, S, EZ)
        o = {k: e[k] for k in ("p10", "f10", "dec10", "p20", "f20", "pass_med")}
        if life:
            o.update(BS.life(T, S, EZ, FZ, n=1000))
        return o
    finally:
        K.qty = old


def cmd_run(tf):
    from tools import scalp_na_lib as N
    from tools import blitz25k_lib as K
    _ledger()
    B = N.bars(tf)
    X = inputs(B)
    T0 = sim(B, X)
    # parity: today's rule == tools/blitz25k_lib.run (the research executor the live rule was checked against)
    ref = K.run(B, {}, "lit+atlas")
    a = [(t["entry_t"], t["exit_t"], round(t["pts"], 2)) for t in T0]
    b = [(t["entry_t"], t["exit_t"], round(t["pts"], 2)) for t in ref]
    parity = {"n": len(a), "n_ref": len(b), "diff": sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))}
    print("parity", parity, flush=True)
    Xa = inputs(B, None)
    Ta = sim(B, Xa)
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "tf": tf, "parity": parity, "spans": {}}
    allT = [t for sp in SPANS_TF[tf] for t in N_span(T0, _spans(B, sp))]
    vx = [N.prev_close("VIX", t["day"]) for t in N_span(T0, _spans(B, "H1" if tf == 1 else "R"))]
    cuts = [float(np.nanpercentile(vx, 33.3)), float(np.nanpercentile(vx, 66.7))]
    out["vix_cuts"] = [round(x, 2) for x in cuts]
    for sp in SPANS_TF[tf]:
        S = _spans(B, sp)
        T = N_span(T0, S)
        if not T:
            continue
        hr = lambda t: f"{t['check'] // 60:02d}:{t['check'] % 60:02d}"  # noqa: E731
        row = {"name": NAMES[sp], "sessions": len(S), "today": fixed(T0, S), "today_plus1tick": fixed(T0, S, 1),
               "alone": fixed(Ta, S), "by_check": group(T, hr), "by_side": group(T, lambda t: "long" if t["dir"] > 0 else "short"),
               "by_break": group(T, lambda t: "first break" if t["brk"] < 2 else "later break"), "by_vix": vix_terc(T, cuts),
               "anatomy": anatomy(T)}
        if sp in ("H1", "H2", "R"):
            row["eval"] = eval_line(T, S, life=True)
        row["ideas"] = {}
        for nm, v in IDEAS.items():
            Tv = sim(B, X, v)
            p, _ = flip_p(Tv, T0, S)
            iv = {"fixed": fixed(Tv, S), "flip_p": p, "exits": group(N_span(Tv, S), lambda t: t["exit_kind"])}
            if sp in ("H1", "H2", "R"):
                iv["eval"] = eval_line(N_span(Tv, S), S)
            row["ideas"][nm] = iv
        out["spans"][sp] = row
        f = row["today"]
        print(sp, f"n {f['n']} tpw {f['tpw']} win {f['win']} pf {f['pf']} net {f['net']} pm {f['per_month']} dd {f['dd']}", flush=True)
        for nm, iv in row["ideas"].items():
            g = iv["fixed"]
            print(f"   {nm:16s} n {g['n']} win {g['win']} pf {g['pf']} pm {g['per_month']} dd {g['dd']} p {iv['flip_p']}"
                  f" ev {iv.get('eval', {}).get('p10')}/{iv.get('eval', {}).get('f10')}", flush=True)
    path = os.path.join(OUT_DIR, f"blitz_review_tf{tf}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("->", os.path.relpath(path, ROOT))
    return 0


# ================================================================================================ verdict
def judge(D):
    """The adopt bar, as written before the run: pick = the idea with the most H1 $ a month that beats today in H1; it passes
    when it also beats today in Jul-Oct and 2021-25 ($ a month at $150, costs in), keeps >= 5 trades a week (a scalper), the
    25K eval's 2-week fails are not up in H1 / Jul-Oct, and the daily sign-flip p is <= 0.2 / cells in both 2026 halves."""
    H1, H2, R = D["spans"]["H1"], D["spans"]["H2"], D["spans"]["R"]
    rows = {}
    for nm in IDEAS:
        a, b, c = H1["ideas"][nm], H2["ideas"][nm], R["ideas"][nm]
        dm = {sp: x["fixed"]["per_month"] - y["today"]["per_month"] for sp, x, y in (("H1", a, H1), ("H2", b, H2), ("R", c, R))}
        rows[nm] = {"title": IDEAS[nm]["title"], "usd_month_by": dm, "flip": {"H1": a["flip_p"], "H2": b["flip_p"]},
                    "win": {"H1": a["fixed"]["win"], "H2": b["fixed"]["win"], "R": c["fixed"]["win"]},
                    "tpw": {"H1": a["fixed"]["tpw"], "H2": b["fixed"]["tpw"], "R": c["fixed"]["tpw"]},
                    "f10": {"H1": a["eval"]["f10"], "H2": b["eval"]["f10"]}, "p10": {"H1": a["eval"]["p10"], "H2": b["eval"]["p10"]}}
    better = [nm for nm in IDEAS if rows[nm]["usd_month_by"]["H1"] > 0]
    pick = max(better, key=lambda nm: rows[nm]["usd_month_by"]["H1"]) if better else None
    thr = round(0.2 / max(1, D.get("lab_cells", len(IDEAS))), 5)
    for nm, r in rows.items():
        why = []
        if r["usd_month_by"]["H1"] <= 0:
            why.append(f"Jan-Jun {r['usd_month_by']['H1']:+,} $/mo")
        if r["usd_month_by"]["H2"] <= 0:
            why.append(f"Jul-Oct {r['usd_month_by']['H2']:+,} $/mo")
        if r["usd_month_by"]["R"] <= 0:
            why.append(f"2021-25 {r['usd_month_by']['R']:+,} $/mo")
        if min(r["tpw"].values()) < 5:
            why.append("under 5 trades a week")
        for sp, nm_ in (("H1", "Jan-Jun"), ("H2", "Jul-Oct")):
            if r["f10"][sp] > rows_base(D, sp)["f10"]:
                why.append(f"{nm_} 2-week eval fails {rows_base(D, sp)['f10']:g} -> {r['f10'][sp]:g}%")
        if not why and (r["flip"]["H1"] > thr or r["flip"]["H2"] > thr):
            why.append(f"could be luck (p {r['flip']['H1']} / {r['flip']['H2']}, needs <= {thr})")
        r["pass"] = not why
        r["why"] = "; ".join(why) or "passes every gate"
    return {"pick": pick, "rows": rows, "p_needed": thr, "passed": [nm for nm in rows if rows[nm]["pass"] and nm == pick]}


def rows_base(D, sp):
    return D["spans"][sp]["eval"]


def cmd_merge():
    A = json.load(open(os.path.join(OUT_DIR, "blitz_review_tf1.json"), encoding="utf-8"))
    Bf = json.load(open(os.path.join(OUT_DIR, "blitz_review_tf5.json"), encoding="utf-8"))
    D = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "date": DATE, "writeup": "research/writeups/blitz-review-2026-11-18.md",
         "ideas": {k: v["title"] for k, v in IDEAS.items()}, "parity": {"1m": A["parity"], "5m": Bf["parity"]},
         "vix_cuts": {"2026 (1m, cut on Jan-Jun)": A["vix_cuts"], "2021-25 (5m)": Bf["vix_cuts"]},
         "spans": {"H1": A["spans"]["H1"], "H2": A["spans"]["H2"], "R": Bf["spans"]["R"]},
         "on_5m": {sp: Bf["spans"][sp]["today"] for sp in ("H1", "H2") if sp in Bf["spans"]},
         "years": {sp: Bf["spans"][sp]["today"] for sp in ("2022", "2023", "2024", "2025") if sp in Bf["spans"]}}
    try:
        from tools import zeus_lab as Z
        exps, forever, _, _ = Z.load_registry()
        mine = sum(1 for e in exps if e.get("kind") == "blitz_idea")
        D["lab_cells"] = Z.cells([e for e in exps if e["kind"] in Z.RUNNABLE]) + (0 if mine else len(IDEAS))
    except Exception:  # noqa: BLE001
        D["lab_cells"] = len(IDEAS)
    D["verdict"] = judge(D)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(D, fh, indent=1)
    v = D["verdict"]
    for nm, r in v["rows"].items():
        print(f"{nm:16s} {r['usd_month_by']}  win {r['win']}  flip {r['flip']}  -> {r['why']}")
    print("pick", v["pick"], "passed", v["passed"], "p_needed", v["p_needed"], "->", os.path.relpath(OUT, ROOT))
    return 0


def lab_result(e: dict, path: str = OUT) -> dict:
    """ZEUS Lab runner for kind blitz_idea: this tool's stored verdict (research/scalp/blitz_review.json; rerun the tool for
    new bars). The $ are BLITZ's own at $150 a trade (costs in); the eval rows are account C's live 25K eval size."""
    D = json.load(open(path, encoding="utf-8"))
    r = (D.get("verdict") or {}).get("rows", {}).get(e.get("idea"))
    if not r:
        return {"proof_ok": False, "why": f"idea {e.get('idea')!r} not in {os.path.relpath(path, ROOT)}", "flip": {}, "deltas": []}
    sp = D["spans"]
    base = {k: {"per_month": sp[k]["today"]["per_month"], "n": sp[k]["today"]["n"], "tpw": sp[k]["today"]["tpw"],
                "pf": sp[k]["today"]["pf"], "net": sp[k]["today"]["net"], "dd": sp[k]["today"]["dd"],
                "p10": (sp[k].get("eval") or {}).get("p10"), "f10": (sp[k].get("eval") or {}).get("f10")} for k in ("H1", "H2", "R")}
    head = {}
    for k in ("H1", "H2", "R"):
        f = sp[k]["ideas"][e["idea"]]["fixed"]
        ev = sp[k]["ideas"][e["idea"]].get("eval") or {}
        head[k] = {"per_month": f["per_month"], "n": f["n"], "tpw": f["tpw"], "pf": f["pf"], "net": f["net"], "dd": f["dd"],
                   "p10": ev.get("p10"), "f10": ev.get("f10")}
    ren = lambda x: {("2021-25" if k == "R" else k): v for k, v in x.items()}  # noqa: E731
    return {"proof_ok": bool(r["pass"]), "why": r["why"], "flip": r["flip"], "head": ren(head), "base": ren(base), "deltas": [],
            "usd_month_by": ren(r["usd_month_by"])}


def cmd_register(log=print):
    from tools import zeus_lab as Z
    D = json.load(open(OUT, encoding="utf-8"))
    for nm, v in IDEAS.items():
        r = D["verdict"]["rows"][nm]
        e = {"id": f"blitz_{nm}", "bot": "blitz", "kind": "blitz_idea", "idea": nm, "registered": DATE, "origin": "claude",
             "source": "research/writeups/blitz-review-2026-11-18.md (tools/blitz_review.py)", "title": f"BLITZ: {v['title']}",
             "what_changes": f"BLITZ (paper scalper) exits: {v['title']}; entries, stop and size unchanged.",
             "hypothesis": "72% of BLITZ's lost $ never reached +0.5R (win-loss-anatomy-2026-11-18.md): cut the trades that do not "
                           "follow through, or leave when price is back inside the noise band, keep the trend-day winners.",
             "judged_by": "blitz_idea", "verdict": r["why"]}
        err = Z.register(e)
        log(f"{e['id']}: {'saved' if not err else err}")
    return 0


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="tools/blitz_review.py")
    ap.add_argument("cmd", choices=("run", "merge", "register"))
    ap.add_argument("--tf", type=int, default=1, choices=(1, 5))
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a.tf)
    return cmd_merge() if a.cmd == "merge" else cmd_register()


if __name__ == "__main__":
    raise SystemExit(_main())
