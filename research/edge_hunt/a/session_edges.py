"""Edge hunt lane A (2026-11-22): NQ RTH session-structure edges LIT does not trade. Paper research only.

PRE-REGISTERED (written before the first run; 14 variants total (12 first run + 2 corrected gap variants C2b/C3b added after C2/C3 produced 0 trades), nothing added after a look, every one is logged):
 ORB  A5 / A15 / A30   opening range of 5 / 15 / 30 min; first 5m close beyond it until 11:30 trades WITH the break;
                       stop 1 tick beyond the OTHER side of the range; target 2R.  (control: repo says plain ORB is dead)
 IBX  B1  first-hour (09:30-10:30) range <= 0.45 x 14-day RTH range ("narrow"), first 5m close beyond it 10:30-14:00 trades the
          extension, stop 1 tick beyond the other IB side, 2R.   B2 same with no width filter (control).
 IBF  B3  failed IB break: a close beyond the IB that closes back inside within 3 bars is faded; stop 1 tick beyond the failed
          extreme; target 2R.   B4 same, target = IB midpoint (needs >= 1R).
 ON   C1  overnight (18:00-09:25) high / low sweep inside the first hour that closes back inside in the SAME bar -> fade;
          stop 1 tick beyond the sweep bar; 2R.  (overlaps the strategy-tree 'overnight' roots; kept because the brief names it)
      C2  open outside the ON range and the 09:30-09:45 close holds beyond the open -> gap-and-go; stop 1 tick beyond the
          opening 15-min opposite extreme; 2R.   C3 = C2 and |gap| >= 0.25 x 14-day range (gap size).
 TREND T1 first-hour drive: |close10:30 - open| >= 0.6 x IB and IB >= 0.5 x 14d range -> enter 10:35 with the drive, stop 1
          tick beyond the extreme of the last 30 min, 2R.   T2 stricter: >= 0.75 x IB, IB >= 0.6 x 14d, first-hour volume
          >= 1.1 x its 20-day mean.
Execution = tools/div_search.walk (the repo's 5m engine: entry next open + 1 tick, stop fill - 1 tick, target needs trade-through,
stop+target same bar = stop, flat 15:55, $1.90/micro round trip, $500 risk a trade, size follows the stop, stop < 8 pts widened to 8).
One trade a day. Judge: H1 2026 (pick), H2 2026 (check), 2025, 2021-24.
    python3 research/edge_hunt/a/session_edges.py
"""
import collections, json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
import div_search as DS
import e2_new_strats as E2
import third_strategy as TS

B = DS.D(); X = E2.Ext(); TICK = DS.TICK; NB = DS.NB
N = len(B.days)
c1130, c1400 = DS.col_of((11, 30)), DS.col_of((14, 0))


def mk(k, j, d, stop, R=2.0, tgt_price=None):
    e = B.O[k, j + 1] + d * TICK
    risk = (e - stop) * d
    if risk <= 0:
        return None
    if risk < 8.0:
        stop = e - d * 8.0; risk = 8.0
    tgt = tgt_price if tgt_price is not None else e + d * R * risk
    if (tgt - e) * d < risk * 0.99:
        return None
    return dict(k=k, j=j, d=d, stop=stop, tgt=tgt)


def sig_orb(m):
    n = m // 5
    def f(k):
        hi, lo = B.H[k, :n].max(), B.L[k, :n].min()
        for j in range(n, c1130 + 1):
            if B.C[k, j] > hi: return mk(k, j, 1, lo - TICK)
            if B.C[k, j] < lo: return mk(k, j, -1, hi + TICK)
    return f


def ib(k):
    return B.H[k, :12].max(), B.L[k, :12].min()


def sig_ibx(narrow):
    def f(k):
        hi, lo = ib(k)
        if narrow and not (hi - lo <= 0.45 * X.rng14[k]): return None
        for j in range(12, c1400 + 1):
            if B.C[k, j] > hi: return mk(k, j, 1, lo - TICK)
            if B.C[k, j] < lo: return mk(k, j, -1, hi + TICK)
    return f


def sig_ibf(mid):
    def f(k):
        hi, lo = ib(k)
        brk = None
        for j in range(12, c1400 + 1):
            c = B.C[k, j]
            if brk is None:
                if c > hi: brk = (1, j)
                elif c < lo: brk = (-1, j)
                continue
            s, j0 = brk
            if j - j0 > 3: return None
            if s == 1 and c <= hi:
                ext = B.H[k, j0:j + 1].max()
                return mk(k, j, -1, ext + TICK, tgt_price=(hi + lo) / 2 if mid else None)
            if s == -1 and c >= lo:
                ext = B.L[k, j0:j + 1].min()
                return mk(k, j, 1, ext - TICK, tgt_price=(hi + lo) / 2 if mid else None)
    return f


def sig_on(k):
    oh, ol = X.ONH[k], X.ONL[k]
    if not (np.isfinite(oh) and np.isfinite(ol)): return None
    for j in range(0, 12):
        if B.H[k, j] > oh and B.C[k, j] <= oh: return mk(k, j, -1, B.H[k, j] + TICK)
        if B.L[k, j] < ol and B.C[k, j] >= ol: return mk(k, j, 1, B.L[k, j] - TICK)


def sig_gap(size):
    def f(k):
        oh, ol, r = X.ONH[k], X.ONL[k], X.rng14[k]
        if not (np.isfinite(oh) and np.isfinite(r)): return None
        o0 = B.O[k, 0]
        if size and not (abs(o0 - B.PC[k]) >= size * r): return None
        if o0 > oh and B.C[k, 2] > o0: return mk(k, 2, 1, B.L[k, :3].min() - TICK)
        if o0 < ol and B.C[k, 2] < o0: return mk(k, 2, -1, B.H[k, :3].max() + TICK)
    return f


def sig_trend(frac, wmin, vmin):
    def f(k):
        hi, lo = ib(k); w = hi - lo; r = X.rng14[k]
        if not np.isfinite(r) or w < wmin * r: return None
        dv = B.C[k, 11] - B.O[k, 0]
        if abs(dv) < frac * w: return None
        if vmin:
            va = X.vavg[k, :12].sum()
            if not np.isfinite(va) or B.V[k, :12].sum() < vmin * va: return None
        if dv > 0: return mk(k, 11, 1, B.L[k, 6:12].min() - TICK)
        return mk(k, 11, -1, B.H[k, 6:12].max() + TICK)
    return f


VARS = {
    "A5_orb5": sig_orb(5), "A15_orb15": sig_orb(15), "A30_orb30": sig_orb(30),
    "B1_ibx_narrow": sig_ibx(True), "B2_ibx_all": sig_ibx(False),
    "B3_ibfail_2R": sig_ibf(False), "B4_ibfail_mid": sig_ibf(True),
    "C1_on_sweep_fade": sig_on, "C2_gap_go_on": sig_gap(0), "C3_gap_go_big": sig_gap(0.25),
    "T1_drive": sig_trend(0.6, 0.5, 0), "T2_drive_strict": sig_trend(0.75, 0.6, 1.1),
}


def sig_gap2(size):
    """Corrected C2/C3 (added after the first run: ON range includes the 09:25 bar, so 'open outside ON' ~never happens).
    Open beyond the PRIOR RTH range (size=0) or a gap >= size x 14d range; 09:45 close holds beyond the open -> go."""
    def f(k):
        r = X.rng14[k]; o0 = B.O[k, 0]
        if not np.isfinite(r) or not np.isfinite(X.PH[k]): return None
        if size:
            if abs(o0 - B.PC[k]) < size * r: return None
        elif not (o0 > X.PH[k] or o0 < X.PL[k]): return None
        up = o0 > B.PC[k]
        if up and B.C[k, 2] > o0: return mk(k, 2, 1, B.L[k, :3].min() - TICK)
        if (not up) and B.C[k, 2] < o0: return mk(k, 2, -1, B.H[k, :3].max() + TICK)
    return f


VARS["C2b_gap_go_outside_PDR"] = sig_gap2(0)
VARS["C3b_gap_go_big"] = sig_gap2(0.25)


def signals(f):
    out = []
    for k in range(N):
        if B.days[k] < "2021-11-15" or not np.isfinite(X.rng14[k]): continue
        s = f(k)
        if s: out.append(s)
    return out


def trades(S, flip=None):
    W = []
    for s in S:
        d, stop, tgt = s["d"], s["stop"], s["tgt"]
        if flip is not None and flip.random() < 0.5:
            e = B.O[s["k"], s["j"] + 1] + d * TICK
            risk, T = (e - stop) * d, (tgt - e) * d
            stop, tgt, d = e + d * risk, e - d * T, -d
        w = DS.walk(B, s["k"], s["j"], d, stop, "fixed", tgt=tgt)
        if w: W.append(w)
    return DS.booked(W)


def report(res, lit, lit_low):
    out = {}
    for nm, r in res.items():
        T = r["_T"]; row = {}
        for sp in ("H1", "H2", "2025", "2021-24", "2021-25"):
            st = r["S"][sp]
            if not st.get("n"): row[sp] = {"n": 0}; continue
            days = TS.span_days(sp)
            own, low = collections.defaultdict(float), collections.defaultdict(float)
            for t in T:
                if days[0] <= t["day"] <= days[-1]:
                    own[t["day"]] += t["pnl"]; low[t["day"]] = min(low[t["day"]], t["low"])
            wins = sorted([v for v in own.values() if v > 0], reverse=True)
            tot = sum(own.values())
            st = dict(st)
            st["best_day_share"] = round(100 * wins[0] / tot) if wins and tot > 0 else None
            y = np.array([own.get(x, 0.0) for x in days]); x_ = np.array([lit.get(x, 0.0) for x in days])
            st["corr_lit"] = round(float(np.corrcoef(x_, y)[0, 1]), 3) if y.std() > 0 and x_.std() > 0 else None
            st["same_day_same_sign_pct"] = round(100 * sum(1 for a, b in zip(x_, y) if a != 0 and b != 0 and (a > 0) == (b > 0)) / max(1, sum(1 for a, b in zip(x_, y) if a != 0 and b != 0)), 0)
            st["eval"] = TS.eval_mc(dict(own), dict(low), sp)
            row[sp] = st
        out[nm] = row
    return out


def main():
    lit = TS.lit_daily()
    d0 = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    lit_low = {x["date"]: float(x.get("low") or 0.0) for x in d0["days"]}
    res = {}
    print("variants tried:", len(VARS))
    for nm, f in VARS.items():
        S = signals(f)
        T = trades(S)
        sc = {sp: DS.stats(T, sp) for sp in ("H1", "H2", "2025", "2021-24", "2021-25")}
        ch = collections.defaultdict(list)
        for seed in range(20):
            Tc = trades(S, flip=np.random.default_rng(seed))
            for sp in ("H1", "H2", "2021-25"):
                ch[sp].append(DS.stats(Tc, sp).get("net", 0))
        res[nm] = {"S": sc, "chance_net_mean": {k: round(float(np.mean(v))) for k, v in ch.items()},
                   "chance_net_max": {k: int(max(v)) for k, v in ch.items()}}
        print(f"{nm:18s} " + " | ".join(f"{sp} n{sc[sp].get('n')} {sc[sp].get('tpw')}/wk WR{sc[sp].get('win')} PF{sc[sp].get('pf')} ${sc[sp].get('net')} DD{sc[sp].get('dd')}" for sp in ("H1", "H2", "2021-25")))
        print("   chance net mean/max:", res[nm]["chance_net_mean"], res[nm]["chance_net_max"])
        res[nm]["_T"] = T
    rep = report(res, lit, lit_low)
    for k in res:
        res[k]["report"] = rep[k]
    json.dump({k: {a: b for a, b in v.items() if a != "_T"} for k, v in res.items()},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_edges.json"), "w"), indent=1)
    return res, lit, lit_low


if __name__ == "__main__":
    main()
