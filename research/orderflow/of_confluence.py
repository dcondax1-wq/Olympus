"""Order flow as CONFLUENCE on LIT / ATLAS trades (pre-registered: research/orderflow/DESIGN_confluence.md, 2026-11-27).

    python -X utf8 research/orderflow/of_confluence.py          # run -> confluence_results.json + confluence_results.md
    python -X utf8 research/orderflow/of_confluence.py --forward   # the PC's forward rows (engine/of_conflog) -> running score

Research only, paper: imports no broker / live module, edits no engine / live_model file. Twin engines: LIT trades re-walked
by `walk_lit` (must equal the engine's $ for every baseline trade), ATLAS through tools/second_md.sim_one itself.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402

ET = ZoneInfo("America/New_York")
TICK, PV = 0.25, 2.0
ABS_SHARE, FLIP_SHARE, SIZE_UP, WIN_BARS = 0.20, 0.25, 1.5, 6
SEED, NBOOT = 20261127, 10000
OUT_J = os.path.join(HERE, "confluence_results.json")
OUT_M = os.path.join(HERE, "confluence_results.md")


def _mod(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


OB = _mod("of_battery.py", "of_battery")


def et_day(ts):
    return OB.et_day(ts)


# ------------------------------------------------------------------------------------------------ OF reads
class Flow:
    """Closed-bar order-flow reads over the OF days."""

    def __init__(self, D):
        self.D = D

    def bars(self, day):
        return self.D[day].bars if day in self.D else None

    def absorbed(self, day, t_bar, d):
        z = self.D[day].zone(int(t_bar), d)
        if z is None:
            return None
        vz, dz = z
        return bool(vz > 0 and dz * d < 0 and abs(dz) >= ABS_SHARE * vz)

    def after(self, day, t_from, n=None):
        """Closed 5m bars whose open >= t_from - 300 + ... : bars that CLOSE at or after t_from (close = open + 300)."""
        b = self.bars(day)
        if b is None:
            return b
        w = b[b.t + 300 > t_from]
        return w if n is None else w.head(n)

    def med_vol_before(self, day, t_bar):
        b = self.bars(day)
        w = b[(b["mod"] >= 570) & (b.t < t_bar)]
        return float(w.volume.median()) if len(w) else 0.0

    def hard_flip(self, day, row, d, entry_d):
        vol = float(row.volume)
        if vol <= 0:
            return False
        dl = float(row.delta)
        close_d = float(row.close) * d
        return (dl * d < 0 and abs(dl) >= FLIP_SHARE * vol and vol >= self.med_vol_before(day, int(row.t))
                and close_d < entry_d)


# ------------------------------------------------------------------------------------------------ LIT twin walker
def walk_lit(B, d, k_fill, entry, stop, tg, q, P, limit_fill, exit_at=None):
    """engine/lit.simulate_x's post-fill loop (live=False, no scale_in / ctx_day / day_mgmt / be_swing / tx), in direction
    space. exit_at(k, be_done) -> True = leave at bar k's open - 1 tick (an OF exit decided at the close before it)."""
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    s_day = B.day[k_fill]
    risk = entry - stop
    be_r, tc, flat = P["be_r"], P.get("t_check"), P["flat_mod"]
    cur, be_done, mfe = stop, False, 0.0
    k, cut, kind, ex = k_fill, None, None, None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; ex, kind = float(c_d[k]) - lit.SLIP, "EOD"; break
        if cut is not None:
            ex, kind = float(o_d[k]) - lit.SLIP, cut; break
        if exit_at is not None and k > k_fill and exit_at(k, be_done):
            ex, kind = float(o_d[k]) - lit.SLIP, "OFX"; break
        if lo_d[k] <= cur:
            ex, kind = cur - lit.SLIP, ("BE" if be_done else "STOP"); break
        if not (k == k_fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                ex, kind = tg, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = entry + float(P.get("be_off") or 0.0), True
        if B.mod[k] >= flat:
            ex, kind = float(c_d[k]) - lit.SLIP, "EOD"; break
        if tc and not be_done and round((B.t[k] - B.t[k_fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
        k += 1
    if ex is None:
        return None
    return {"pnl": (ex - entry) * PV * q - lit.COMM * q, "exit": kind, "exit_k": k, "r": (ex - entry) / risk - lit.COMM / (PV * risk),
            "q": q, "entry": entry}


def lit_setup():
    from tools import lit_final as F
    from tools import lit_adopt_combo as AC
    P = {**lit.DEFAULTS, **AC.LIVE, "t_check": AC.T15, "be_off": AC.BE_OFF}
    M, C = F.market(P["ref"], P["extra_boxes"])
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    # F.SESS = the stored baseline's days (ends 2026-10-14); after its last day every market day counts (sessions=None),
    # checked: the same trades as F.SESS up to that day
    T_all = lit.run_x(M, C, P, None, B1=B1, B5=B5)
    last = max(F.SESS)
    T = [t for t in T_all if t["day"] in set(F.SESS) or t["day"] > last]
    return P, M, B1, B5, T


def lit_ideas(Fl, P, M, B1, B5, T):
    rows, bad = [], 0
    for t in T:
        day = et_day(t["entry_t"])
        if day not in Fl.D or t.get("tf") != 1:
            continue
        B = B1
        d = int(t["dir"])
        entry, stop, tg = float(t["entry_px"]) * d, float(t["stop_px"]) * d, float(t["target_px"]) * d
        q = int(t["qty"]); k_fill = int(t["fill_k"]) if "fill_k" in t else int(np.searchsorted(B.t, int(t["entry_t"])))
        lf = bool(t.get("limit_fill", False))
        base = walk_lit(B, d, k_fill, entry, stop, tg, q, P, lf)
        if base is None or abs(base["pnl"] - float(t["pnl"])) > 1.0:
            bad += 1
            continue
        row = {"day": t["day"], "et": day, "dir": d, "base": base["pnl"], "base_r": base["r"], "exit": base["exit"], "q": q}
        # sweep-extreme bar (OF1 read, as the battery): t["ext_i"] in the Market
        ext_t = int(M.t[t["ext_i"]]) if t.get("ext_i") is not None else None
        ab = Fl.absorbed(et_day(ext_t), ext_t, d) if ext_t is not None and et_day(ext_t) in Fl.D else None
        row["absorbed"] = ab
        # C-b size up
        q2 = min(lit.MAX_MICROS, int(q * SIZE_UP)) if ab else q
        row["b"] = base["pnl"] * q2 / q if q2 != q else base["pnl"]
        row["b_q"] = q2
        # C-c hard-flip exit before BE
        fb = Fl.bars(day)
        flips = [int(r.t) + 300 for r in fb.itertuples() if int(r.t) + 300 > int(B.t[k_fill]) and Fl.hard_flip(day, r, d, entry)]

        def exit_at(k, be_done, flips=flips):
            return (not be_done) and any(int(B.t[k - 1]) + 60 <= f <= int(B.t[k]) for f in flips)

        c = walk_lit(B, d, k_fill, entry, stop, tg, q, P, lf, exit_at=exit_at)
        row["c"] = c["pnl"] if c else base["pnl"]; row["c_exit"] = c["exit"] if c else base["exit"]
        # C-a absorbed-bar entry timing
        row["a"], row["a_note"], row["a_ticks"] = timing_lit(Fl, B, d, day, k_fill, entry, stop, tg, P)
        rows.append(row)
    return rows, bad


def timing_lit(Fl, B, d, day, k_fill, entry, stop, tg, P):
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t_fill = int(B.t[k_fill])
    w = Fl.after(day, t_fill, WIN_BARS)
    for r in w.itertuples():
        t_close = int(r.t) + 300
        # price path from the fill to this close: stop / target touched first -> missed
        k1 = int(np.searchsorted(B.t, t_close))
        if k1 > k_fill and (lo_d[k_fill:k1].min() <= stop or hi_d[k_fill:k1].max() >= tg):
            return 0.0, "missed (stop/target first)", None
        if not Fl.absorbed(day, int(r.t), d):
            continue
        if k1 >= B.n or B.day[k1] != B.day[k_fill]:
            return 0.0, "missed (day end)", None
        e2 = float(o_d[k1]) + lit.SLIP
        risk = e2 - stop
        if risk <= 0 or not (P["min_stop"] <= risk <= P["max_stop"]) or tg - e2 < 1.0 * risk:
            return 0.0, "missed (risk/target)", None
        q2 = lit.qty_for(risk)
        if q2 < 1:
            return 0.0, "missed (size)", None
        res = walk_lit(B, d, k1, e2, stop, tg, q2, P, False)
        if res is None:
            return 0.0, "missed (no exit)", None
        return res["pnl"], "entered", round((entry - e2) / TICK, 1)
    return 0.0, "missed (no absorbed bar)", None


# ------------------------------------------------------------------------------------------------ ATLAS (MD) via sim_one
def atlas_setup():
    from tools import second_md as SM
    v = json.load(open(os.path.join(ROOT, "research", "second", "md_best.json"), encoding="utf-8"))
    X = SM.ctx_full()
    T = SM.trades_of(X, {"fam": "md", **v["params"]})
    return SM, X, v, T


def atlas_ideas(Fl, SM, X, v, T):
    sim = v["params"]["sim"]
    rows, bad = [], 0
    for z, r in T:
        day = et_day(int(X.Xt[r["x0"]]))
        if day not in Fl.D:
            continue
        d = int(z["dir"])
        q = SM.q_usd(500.0, r["risk"])
        if q <= 0:
            continue
        per = lambda rr: rr["pts"] * PV - SM.COMM                       # noqa: E731
        base = q * per(r)
        row = {"day": X.dates[X.Xday[r["x0"]]], "et": day, "dir": d, "base": base, "base_r": SM.r_of(r), "q": q,
               "exit": r["kind"]}
        tN = int(X.Xt[r["x0"]])
        fb = Fl.bars(day)
        w = fb[(fb.t + 300 <= tN)].tail(6)
        ab = None
        if len(w) >= 6:
            j = w.low.idxmin() if d == 1 else w.high.idxmax()
            ab = Fl.absorbed(day, int(fb.at[j, "t"]), d)
        row["absorbed"] = ab
        q2 = min(40, int(q * SIZE_UP)) if ab else q
        row["b"] = q2 * per(r); row["b_q"] = q2
        # C-c2 hard flip before +1R MFE -> force_t = the flip bar's close (sim_one exits at the open of the first bar >= it)
        e_d = r["e"] * d
        ft = None
        for rr in fb[fb.t >= tN].itertuples():
            tc = int(rr.t) + 300
            if tc > int(X.Xe[r["x1"]]):
                break
            k = int(np.searchsorted(X.Xt, tc)) - 1
            seg = slice(r["x0"], k + 1)
            mfe = ((X.Xh[seg].max() if d == 1 else -X.Xl[seg].min()) - e_d) / r["risk"]
            if mfe >= 1.0:
                break
            if Fl.hard_flip(day, rr, d, e_d):
                ft = tc; break
        if ft is not None:
            rc = SM.sim_one(X, z, sim["ent"], sim["tgt"], sim["be"], sim["tc"], sim.get("stop", "ext"), force_t=ft)
            row["c"] = q * per(rc) if rc else base; row["c_exit"] = rc["kind"] if rc else r["kind"]
        else:
            row["c"] = base; row["c_exit"] = r["kind"]
        # C-d delayed entry to the first non-adverse closed bar
        row["d"], row["d_note"], row["d_ticks"] = delayed_atlas(Fl, SM, X, z, r, sim, day, d)
        rows.append(row)
    return rows, bad


def delayed_atlas(Fl, SM, X, z, r, sim, day, d):
    j = z["j"]
    fb = Fl.bars(day)
    i = fb.index[fb.t == int(X.t[j])]
    if not len(i):
        return None, "no OF bar", None
    i = int(i[0])
    if float(fb.at[i, "delta"]) * d >= 0:
        q = SM.q_usd(500.0, r["risk"])
        return q * (r["pts"] * PV - SM.COMM), "unchanged", 0.0
    stop = z["stops"][sim.get("stop", "ext")]
    for s in range(1, WIN_BARS + 1):
        ii = i + s
        if ii >= len(fb):
            break
        jj = j + s
        if jj >= X.n or X.day[jj] != X.day[j]:
            break
        # stop touched while waiting -> missed
        hi, lo = X.h[j + 1:jj + 1].max(), X.l[j + 1:jj + 1].min()
        if (d == 1 and lo <= stop) or (d == -1 and hi >= stop):
            return 0.0, "missed (stop first)", None
        if int(X.t[jj]) != int(fb.at[ii, "t"]):
            return None, "bar mismatch", None
        if float(fb.at[ii, "delta"]) * d >= 0:
            z2 = dict(z); z2["j"] = jj
            r2 = SM.sim_one(X, z2, sim["ent"], sim["tgt"], sim["be"], sim["tc"], sim.get("stop", "ext"))
            if r2 is None:
                return 0.0, "missed (risk/target)", None
            q2 = SM.q_usd(500.0, r2["risk"])
            if q2 <= 0:
                return 0.0, "missed (size)", None
            return q2 * (r2["pts"] * PV - SM.COMM), "delayed", round((r["e"] - r2["e"]) * d / TICK, 1)
    return 0.0, "missed (no non-adverse bar)", None


# ------------------------------------------------------------------------------------------------ scoring
def pf(x):
    x = np.asarray(x, float)
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    return round(float(g / l), 2) if l > 0 else None


def score(rows, key, rng):
    rows = [r for r in rows if r.get(key) is not None]
    if not rows:
        return {"n": 0}
    base = np.array([r["base"] for r in rows]); var = np.array([r[key] for r in rows])
    gain = var - base
    days = sorted({r["et"] for r in rows})
    by = {d: gain[[i for i, r in enumerate(rows) if r["et"] == d]].sum() for d in days}
    g = np.array([by[d] for d in days])
    boot = rng.choice(g, size=(NBOOT, len(g)), replace=True).sum(1) if len(g) else np.zeros(1)
    allD = sorted(set(OB_DAYS))
    half = allD[min(len(allD) - 1, (len(allD) + 1) // 2)] if allD else "9999"   # frozen split (51 days: index 26)
    h1 = float(sum(by[d] for d in days if d < half)); h2 = float(sum(by[d] for d in days if d >= half))
    changed = int((np.abs(gain) > 0.005).sum())
    top = int(np.argmax(gain)) if len(gain) else 0
    loo = float(gain.sum() - gain[top]) if len(gain) else 0.0
    verdict = ("TOO FEW" if changed < 10 else "CANDIDATE" if (h1 > 0 and h2 > 0) else
               "WORSE" if (h1 <= 0 and h2 <= 0) else "MIXED")
    return {"n": len(rows), "changed": changed, "base_usd": round(float(base.sum())), "var_usd": round(float(var.sum())),
            "gain_usd": round(float(gain.sum())), "pf_base": pf(base), "pf_var": pf(var),
            "win_base": round(100 * float((base > 0).mean()), 1), "win_var": round(100 * float((var > 0).mean()), 1),
            "ci95": [round(float(np.percentile(boot, 2.5))), round(float(np.percentile(boot, 97.5)))],
            "p_gain_le0": round(float((boot <= 0).mean()), 3), "half_old": round(h1), "half_new": round(h2), "verdict": verdict,
            "gain_wo_best": round(loo), "best_trade": [rows[top]["day"], round(float(gain[top]))] if len(gain) else None}


OB_DAYS = []


def run():
    R = OB.find_days()
    D = {d: OB.Day(d, R[d]) for d in sorted(R) if int(R[d]["meta"].get("rows", 0)) >= OB.MIN_ROWS}   # battery's thin-day rule
    if not D:
        print("0 OF days: run python -X utf8 tools/data_pull.py --of --no-battery first"); return None
    OB_DAYS[:] = sorted(D)
    Fl = Flow(D)
    rng = np.random.default_rng(SEED)
    P, M, B1, B5, T = lit_setup()
    L, bad_l = lit_ideas(Fl, P, M, B1, B5, T)
    SM, X, v, TA = atlas_setup()
    A, bad_a = atlas_ideas(Fl, SM, X, v, TA)
    out = {"built": "2026-11-27", "of_days": [OB_DAYS[0], OB_DAYS[-1], len(OB_DAYS)], "prereg": "DESIGN_confluence.md",
           "lit": {"trades": len(L), "twin_mismatch": bad_l, "absorbed": sum(1 for r in L if r["absorbed"]),
                   "C-a timing": score(L, "a", rng), "C-b size": score(L, "b", rng), "C-c flip exit": score(L, "c", rng),
                   "a_notes": _count(L, "a_note"), "a_ticks_mean": _mean([r["a_ticks"] for r in L if r["a_ticks"] is not None]),
                   "c_exits": sum(1 for r in L if r["c_exit"] == "OFX")},
           "atlas": {"trades": len(A), "absorbed": sum(1 for r in A if r["absorbed"]),
                     "C-b2 size": score(A, "b", rng), "C-c2 flip exit": score(A, "c", rng), "C-d delayed entry": score(A, "d", rng),
                     "d_notes": _count(A, "d_note"), "d_ticks_mean": _mean([r["d_ticks"] for r in A if r["d_ticks"]]),
                     "c_exits": sum(1 for r in A if r["c_exit"] == "lit")},
           "rows": {"lit": _clean(L), "atlas": _clean(A)}}
    json.dump(out, open(OUT_J, "w", encoding="utf-8"), indent=1, default=float)
    write_md(out)
    return out


def _count(R, k):
    c = {}
    for r in R:
        c[r[k]] = c.get(r[k], 0) + 1
    return c


def _mean(x):
    return round(float(np.mean(x)), 2) if x else None


def _clean(R):
    return [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in R]


def write_md(o):
    L, A = o["lit"], o["atlas"]

    def line(nm, s):
        if not s.get("n"):
            return f"| {nm} | 0 | | | | | | | |"
        return (f"| {nm} | {s['n']} ({s['changed']} changed) | ${s['base_usd']:+,} -> ${s['var_usd']:+,} | **${s['gain_usd']:+,}** "
                f"| {s['pf_base']} -> {s['pf_var']} | ${s['ci95'][0]:+,} .. ${s['ci95'][1]:+,} | ${s['half_old']:+,} / ${s['half_new']:+,} "
                f"| ${s['gain_wo_best']:+,} | {s['verdict']} |")
    hdr = ("| idea | trades | $ base -> idea | gain | PF | 95% CI of gain (day bootstrap) | old / new half | gain without its best trade "
           "| verdict |\n|---|---|---|---|---|---|---|---|---|")
    s = [f"# Order flow as confluence: results ({o['built']})", "",
         f"Pre-registered: `DESIGN_confluence.md`. OF days: {o['of_days'][2]} ({o['of_days'][0]} .. {o['of_days'][1]}). "
         "Costs in. Research only - nothing here changes a bot.", "",
         f"## LIT ({L['trades']} trades on OF days; twin mismatches dropped: {L['twin_mismatch']}; sweep bar absorbed: {L['absorbed']})", "",
         hdr, line("C-a enter on first absorbed bar", L["C-a timing"]), line("C-b 1.5x size when absorbed", L["C-b size"]),
         line("C-c exit on hard flip (before BE)", L["C-c flip exit"]), "",
         f"C-a outcomes: {L['a_notes']}; mean entry change {L['a_ticks_mean']} ticks (+ = better). C-c fired on {L['c_exits']} trades.", "",
         f"## ATLAS MD ({A['trades']} trades on OF days; sweep bar absorbed: {A['absorbed']})", "",
         hdr, line("C-b2 1.5x size when absorbed", A["C-b2 size"]), line("C-c2 exit on hard flip (before 1R)", A["C-c2 flip exit"]),
         line("C-d delay to first non-adverse delta bar", A["C-d delayed entry"]), "",
         f"C-d outcomes: {A['d_notes']}; mean entry change on delayed trades {A['d_ticks_mean']} ticks (+ = better).", ""]
    s += [open(os.path.join(HERE, "confluence_notes.md"), encoding="utf-8").read()] if os.path.exists(
        os.path.join(HERE, "confluence_notes.md")) else []
    open(OUT_M, "w", encoding="utf-8").write("\n".join(s) + "\n")


# ------------------------------------------------------------------------------------------------ FORWARD score (night-of-conflog)
FWD_FROM = "2026-11-28"                     # forward days only: the first session after this pre-registration
JUDGE = {"lit": 30, "atlas": 20}            # LEAD_WIRES: judge at ~30 LIT / ~20 ATLAS forward trades
OUT_F = os.path.join(HERE, "confluence_forward.json")
ATLAS_P = {"be_r": None, "flat_mod": 955, "be_off": 0.0, "t_check": {"at": 15, "x": 0.3, "mfe": 0.5}}   # MD: no BE, T15, flat 15:55


def forward_rows(src=None):
    """The PC's nightly rows (engine/of_conflog.py) from data/pc_days/<day>/of/NQ_conflog.json.gz, days >= FWD_FROM."""
    import glob
    import gzip
    base = src or os.path.join(ROOT, "data", "pc_days")
    out = []
    for p in sorted(glob.glob(os.path.join(base, "*", "of", "NQ_conflog.json.gz"))):
        day = os.path.basename(os.path.dirname(os.path.dirname(p)))
        if day < FWD_FROM:
            continue
        try:
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        out += [r for r in doc.get("rows") or [] if isinstance(r, dict) and not r.get("error") and r.get("pnl") is not None]
    return out


def _gains(r, B1, P):
    """{idea: $ gain vs the real trade} for one forward row (None = idea not applicable / not computable)."""
    d, q, pnl = int(r["d"]), int(r.get("qty") or 0), float(r["pnl"])
    g = {}
    if q >= 1:
        q2 = min(lit.MAX_MICROS, int(q * SIZE_UP)) if r.get("sweep_read") == "absorbed" else q
        g["b"] = pnl * (q2 - q) / q
    entry = float(r.get("fill") or r.get("entry") or 0) * d
    stop, tg = float(r["stop"]) * d, (float(r["target"]) * d if r.get("target") else None)
    if B1 is None or not entry or tg is None or q < 1:
        return g
    PP = P if r["bot"] == "lit" else {**P, **ATLAS_P}
    k0 = int(np.searchsorted(B1.t, int(r.get("tf") or r["t"])))
    if k0 >= B1.n:
        return g
    base = walk_lit(B1, d, k0, entry, stop, tg, q, PP, False)
    if base is None:
        return g
    if r.get("hard1_t"):                     # C-c: leave at the first 1m open at / after the hard-flip bar's close, before BE
        ft = int(r["hard1_t"])
        c = walk_lit(B1, d, k0, entry, stop, tg, q, PP, False, exit_at=lambda k, be: (not be) and int(B1.t[k]) >= ft > int(B1.t[k - 1]))
        g["c"] = (c["pnl"] if c else base["pnl"]) - base["pnl"]
    else:
        g["c"] = 0.0
    key, tt = ("a", r.get("abs1_t")) if r["bot"] == "lit" else ("d", r.get("nonadv1_t"))
    if r["bot"] == "atlas" and r.get("sig_delta") is not None and float(r["sig_delta"]) * d >= 0:
        g["d"] = 0.0                          # signal bar already non-adverse: unchanged
    elif not tt:
        g[key] = -base["pnl"]                 # no confirming bar in the window: the trade is MISSED
    else:
        k1 = int(np.searchsorted(B1.t, int(tt)))
        hi_d, lo_d, _c, o_d = B1.dirs(d)
        if k1 >= B1.n or (k1 > k0 and (lo_d[k0:k1].min() <= stop or hi_d[k0:k1].max() >= tg)):
            g[key] = -base["pnl"]
        else:
            e2 = float(o_d[k1]) + lit.SLIP
            risk = e2 - stop
            q2 = lit.qty_for(risk) if r["bot"] == "lit" else max(0, min(40, int(500.0 / (risk * PV)))) if risk > 0 else 0
            v = walk_lit(B1, d, k1, e2, stop, tg, q2, PP, False) if risk > 0 and q2 >= 1 and tg - e2 >= 1.0 * risk else None
            g[key] = (v["pnl"] if v else 0.0) - base["pnl"]
    return g


def forward(say=print, src=None, write=True):
    """The running forward score per idea vs the LEAD_WIRES judge rule. Paper research; writes confluence_forward.json."""
    rows = forward_rows(src)
    B1 = P = None
    if rows:
        try:
            from tools import lit_final as F
            from tools import lit_adopt_combo as AC
            P = {**lit.DEFAULTS, **AC.LIVE, "t_check": AC.T15, "be_off": AC.BE_OFF}
            M, _ = F.market(P["ref"], P["extra_boxes"])
            B1 = F.bars(M, "1m")
        except Exception as e:  # noqa: BLE001
            say(f"confluence forward: no 1m bars ({e.__class__.__name__}): only C-b scored")
    ideas = {"lit": ("a", "b", "c"), "atlas": ("b", "c", "d")}
    names = {"a": "C-a absorbed-bar entry", "b": "C-b 1.5x when absorbed", "c": "C-c hard-flip exit", "d": "C-d non-adverse entry"}
    out = {"fwd_from": FWD_FROM, "rows": len(rows), "ideas": {}}
    G = [(r, _gains(r, B1, P or lit.DEFAULTS)) for r in rows]
    for bot, keys in ideas.items():
        mine = [(r, g) for r, g in G if r.get("bot") == bot]
        days = sorted({r["day"] for r, _ in mine})
        half = days[len(days) // 2] if days else "9999"          # older half = days before it (1 day: all "new")
        for k in keys:
            xs = [(r["day"], g[k]) for r, g in mine if g.get(k) is not None]
            gs = [x for _, x in xs]
            n, need = len(xs), JUDGE[bot]
            tot = float(sum(gs)); wo = tot - max(gs) if gs else 0.0
            h1 = float(sum(x for dd, x in xs if dd < half)); h2 = float(sum(x for dd, x in xs if dd >= half))
            state = (f"logging ({n} of {need})" if n < need else
                     "PASSES the judge rule: owner card" if (h1 > 0 and h2 > 0 and wo > 0) else "FAILS the judge rule")
            out["ideas"][f"{bot}:{k}"] = {"name": names[k], "n": n, "need": need, "gain_usd": round(tot), "gain_wo_best": round(wo),
                                         "half_old": round(h1), "half_new": round(h2), "state": state}
            say(f"confluence {bot.upper():5s} {names[k]:26s} n {n:3d}/{need}  gain ${tot:+,.0f} (without best ${wo:+,.0f}; "
                f"halves ${h1:+,.0f} / ${h2:+,.0f})  {state}")
    if write:
        json.dump(out, open(OUT_F, "w", encoding="utf-8"), indent=1)
    return out


if __name__ == "__main__":
    if "--forward" in sys.argv:
        forward()
        sys.exit(0)
    o = run()
    if o:
        print(open(OUT_M, encoding="utf-8").read())
