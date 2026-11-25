"""IDEA MILL runner (research/ideamill/DESIGN.md). PAPER RESEARCH ONLY: never trades, sizes, arms or edits a live file.

    python -X utf8 tools/ideamill.py --batch 200          # nightly light: 200 grammar ideas not tried yet (no network, 20 min cap)
    python -X utf8 tools/ideamill.py --batch 0            # every grammar idea not tried yet
    python -X utf8 tools/ideamill.py --harvest            # weekly: arXiv q-fin + NBER abstracts -> mapped ideas / needs a human
    python -X utf8 tools/ideamill.py --report             # the gate counts + the survivors
    python -X utf8 tools/ideamill.py --of                 # the order-flow grammar only (research/orderflow/DESIGN_forward.md):
                                                          # off under 60 tick days, its own 60/40 split, runs in every --batch too
Outputs (research/ideamill/): trials.jsonl.gz (EVERY trial, the running count on each line), summary.json (the Brain reads it),
harvest.json, needs_human.json, rejected_registry.json; survivors -> research/learn/journal.json (pillar market, lens idea mill).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "ideamill"))
OUT = os.path.join(ROOT, "research", "ideamill")
TRIALS = os.path.join(OUT, "trials.jsonl.gz")          # gzip members appended per run (git-friendly)
SUMMARY = os.path.join(OUT, "summary.json")
DISC = ("2021-11-01", "2024-12-31")
HOLD = {"2025": ("2025-01-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16")}
MIN_DISC, MIN_HOLD, Q_FDR, DSR_MIN, PF_HOLD, FWD_MIN = 100, 10, 0.10, 0.95, 1.10, 20
B, BLOCK = 1000, 5
PROTO = 3                       # DESIGN_v3.md (family-first); proto 1 / 2 rows are kept in the log, not counted
CONFIRM_FAMILY = "1h|vwap_band|fade|nypm|"     # DESIGN_v3 pre-designated confirmation track
CONFIRM_NAMED = "1h|vwap_band|fade|nypm|none|atr|T12"


# ================================================================================================ statistics
def daily_series(d_idx, r, X, span):
    days = X["udays"]
    a, z = span
    sel = (days >= a) & (days <= z)
    ix = np.flatnonzero(sel)
    pos = {int(k): j for j, k in enumerate(ix)}
    x = np.zeros(len(ix))
    for k, v in zip(d_idx, r):
        j = pos.get(int(k))
        if j is not None:
            x[j] += v
    return x


_W = {}


def boot_weights(nd, seed=11):
    """B x nd moving-block bootstrap counts (how often each day appears in each draw)."""
    if nd not in _W:
        rng = np.random.default_rng(seed)
        W = np.zeros((B, nd))
        nb = int(math.ceil(nd / BLOCK))
        starts = rng.integers(0, nd - BLOCK + 1, size=(B, nb))
        for b in range(B):
            idx = (starts[b][:, None] + np.arange(BLOCK)[None, :]).ravel()[:nd]
            np.add.at(W[b], idx, 1.0)
        _W[nd] = W
    return _W[nd]


def boot_p(x):
    """One-sided p (mean > 0) vs the demeaned series, moving-block bootstrap."""
    nd = len(x)
    m = x.mean()
    W = boot_weights(nd)
    null = W @ (x - m) / nd
    se = float(null.std(ddof=1))
    if se <= 0:
        return 1.0
    from statistics import NormalDist
    return float(1.0 - NormalDist().cdf(m / se))


def sharpe(x):
    s = x.std(ddof=1)
    return float(x.mean() / s) if s > 0 else 0.0


def dsr(x, n_trials, var_sr):
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) of a daily series."""
    from math import erf, sqrt
    from statistics import NormalDist
    N = max(2, n_trials)
    g = 0.5772156649
    Z = NormalDist().inv_cdf
    sr0 = sqrt(max(var_sr, 1e-12)) * ((1 - g) * Z(1 - 1 / N) + g * Z(1 - 1 / (N * math.e)))
    sr = sharpe(x)
    T = len(x)
    sk = float(((x - x.mean()) ** 3).mean() / (x.std() ** 3 + 1e-12))
    ku = float(((x - x.mean()) ** 4).mean() / (x.std() ** 4 + 1e-12))
    den = sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4 * sr * sr))
    z = (sr - sr0) * sqrt(T - 1) / den
    return 0.5 * (1 + erf(z / sqrt(2))), sr0


def pf(r):
    g, l = r[r > 0].sum(), -r[r < 0].sum()
    return float(g / l) if l > 0 else (99.0 if g > 0 else 0.0)


def bh(pvals, q=Q_FDR):
    """Benjamini-Hochberg: boolean pass per p (same order)."""
    p = np.asarray(pvals, float)
    m = len(p)
    if not m:
        return np.zeros(0, bool)
    o = np.argsort(p)
    thr = q * (np.arange(1, m + 1)) / m
    ok = p[o] <= thr
    k = np.max(np.flatnonzero(ok)) + 1 if ok.any() else 0
    res = np.zeros(m, bool)
    res[o[:k]] = True
    return res


# ================================================================================================ trials log
def load_trials():
    T = []
    if os.path.exists(TRIALS):
        import gzip
        with gzip.open(TRIALS, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    T.append(json.loads(line))
    return T


def span_stats(d, r, X, span):
    days = X["udays"][d]
    m = (days >= span[0]) & (days <= span[1])
    rr = r[m]
    return {"n": int(m.sum()), "mean_r": round(float(rr.mean()), 4) if len(rr) else None, "pf": round(pf(rr), 3) if len(rr) else None,
            "sum_r": round(float(rr.sum()), 2)}


def score_one(X, I, data_end):
    import grammar as G
    row = {"id": I["id"], "proto": PROTO, "spec": I, "data_end": data_end, "t": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")}
    if I["trigger"] in G.NEEDS:
        row.update(status="untestable", why=G.NEEDS[I["trigger"]])
        return row
    d, r, g = G.run_idea(X, I)
    x = daily_series(d, r, X, DISC)
    ds = span_stats(d, r, X, DISC)
    row["disc"] = {**ds, "days": len(x)}
    if ds["n"] < MIN_DISC:
        row["status"] = "too_few"
        return row
    row["disc"].update(p=round(boot_p(x), 5), sr=round(sharpe(x), 5))
    row["status"] = "scored"
    rp = placebo_r(I["id"], r, g)
    m = (X["udays"][d] >= DISC[0]) & (X["udays"][d] <= DISC[1])
    xp = daily_series(d, rp, X, DISC)
    row["placebo"] = {"mean_r": round(float(rp[m].mean()), 4), "p": round(boot_p(xp), 5), "sr": round(sharpe(xp), 5)}
    return row


def placebo_r(iid, r, g):
    """Each trade's gross R sign flipped at random (seeded by the idea id), costs kept."""
    rng = np.random.default_rng(zlib.crc32(iid.encode()))
    return rng.choice([-1.0, 1.0], size=len(g)) * g - (g - r)


def gates(T_all, X, say):
    """G1-G3 over EVERY scored trial ever (BH and DSR use the full count). Only the ideas that pass a gate are re-run."""
    import grammar as G
    T_all = [t for t in T_all if t.get("proto") == PROTO]
    sc = [t for t in T_all if t.get("status") == "scored"]
    N = len(T_all)
    srs = np.array([t["disc"]["sr"] for t in sc]) if sc else np.zeros(0)
    var_sr = float(srs.var()) if len(srs) > 1 else 0.0
    pl_var = float(np.var([t["placebo"]["sr"] for t in sc])) if len(sc) > 1 else 0.0
    counts = {"trials_total": N, "scored": len(sc), "too_few": sum(1 for t in T_all if t.get("status") == "too_few"),
              "untestable": sum(1 for t in T_all if t.get("status") == "untestable"),
              "discovery_mean_positive": sum(1 for t in sc if (t["disc"]["mean_r"] or 0) > 0),
              "raw_p_below_0.05": sum(1 for t in sc if t["disc"]["p"] < 0.05 and (t["disc"]["mean_r"] or 0) > 0),
              "G1_bh": 0, "G2_dsr": 0, "G3_holdouts": 0, "G4_forward": 0, "placebo_G1": 0, "placebo_G2": 0, "placebo_G3": 0}
    ok = bh([t["disc"]["p"] for t in sc])
    pok = bh([t["placebo"]["p"] for t in sc])
    def hold_ok(H):
        return all(H[h]["n"] >= MIN_HOLD and (H[h]["mean_r"] or 0) > 0 and (H[h]["pf"] or 0) >= PF_HOLD for h in H)
    for t, o_, po in zip(sc, ok, pok):
        t["gate"] = "G0"
        real = o_ and (t["disc"]["mean_r"] or 0) > 0
        plac = po and (t["placebo"]["mean_r"] or 0) > 0
        if not (real or plac):
            continue
        d, r, g = G.run_idea(X[t["spec"]["tf"]], t["spec"])
        XX = X[t["spec"]["tf"]]
        if real:
            t["gate"] = "G1"; counts["G1_bh"] += 1
            v, sr0 = dsr(daily_series(d, r, XX, DISC), N, var_sr)
            t["disc"]["dsr"], t["disc"]["sr0"] = round(v, 4), round(sr0, 5)
            if v >= DSR_MIN:
                t["gate"] = "G2"; counts["G2_dsr"] += 1
                t["hold"] = {h: span_stats(d, r, XX, sp) for h, sp in HOLD.items()}
                if hold_ok(t["hold"]):
                    t["gate"] = "G3"; counts["G3_holdouts"] += 1
        if plac:
            counts["placebo_G1"] += 1
            rp = placebo_r(t["id"], r, g)
            v, _ = dsr(daily_series(d, rp, XX, DISC), N, pl_var)
            if v >= DSR_MIN:
                counts["placebo_G2"] += 1
                if hold_ok({h: span_stats(d, rp, XX, sp) for h, sp in HOLD.items()}):
                    counts["placebo_G3"] += 1
    counts["expected_false_G1_bh_bound"] = round(Q_FDR * counts["G1_bh"], 1)
    counts["expected_raw_p05_by_luck"] = round(0.05 * len(sc), 0)
    return counts


# ================================================================================================ v3: family-first
def simes(p):
    p = np.sort(np.asarray(p, float))
    m = len(p)
    return float(min(1.0, np.min(p * m / np.arange(1, m + 1)))) if m else 1.0


def hier(T_all, X, say):
    """DESIGN_v3: Stage A BH over families (Simes p), Stage B BH inside passing families at q R / F, C DSR, D hold-outs.
    Same for the placebo. Returns (counts, families table, survivors)."""
    import grammar as G
    sc = [t for t in T_all if t.get("status") == "scored"]
    fam = {}
    for t in sc:
        fam.setdefault((t["spec"]["trigger"], t["spec"]["dir"]), []).append(t)
    keys = sorted(fam)
    F = len({(I["trigger"], I["dir"]) for I in G.ideas()})
    out = {}
    for lab, pk, mk in (("real", "disc", "mean_r"), ("placebo", "placebo", "mean_r")):
        fp = [simes([t[pk]["p"] for t in fam[k]]) for k in keys]
        okA = bh(fp, Q_FDR)
        R = int(okA.sum())
        rows, surv = [], []
        for k, p_, a in zip(keys, fp, okA):
            row = {"family": f"{k[0]}|{k[1]}", "variants": len(fam[k]), "simes_p": round(p_, 6), "stageA": bool(a),
                   "best_p": round(min(t[pk]["p"] for t in fam[k]), 6),
                   "positive": sum(1 for t in fam[k] if (t[pk][mk] or 0) > 0)}
            if a:
                qB = Q_FDR * R / F
                okB = bh([t[pk]["p"] for t in fam[k]], qB)
                passB = [t for t, o in zip(fam[k], okB) if o and (t[pk][mk] or 0) > 0]
                row["stageB"] = len(passB)
                nC = nD = 0
                srs = np.array([t[pk]["sr"] for t in fam[k]])
                for t in passB:
                    XX = X[t["spec"]["tf"]]
                    d, r, g = G.run_idea(XX, t["spec"])
                    rr = r if lab == "real" else placebo_r(t["id"], r, g)
                    v, _ = dsr(daily_series(d, rr, XX, DISC), len(fam[k]), float(srs.var()))
                    if v < DSR_MIN:
                        continue
                    nC += 1
                    H = {h: span_stats(d, rr, XX, sp) for h, sp in HOLD.items()}
                    okH = all(H[h]["n"] >= MIN_HOLD and (H[h]["mean_r"] or 0) > 0 and (H[h]["pf"] or 0) >= PF_HOLD for h in H)
                    if lab == "real":
                        t["gate"] = "D" if okH else "C"
                        t["disc"]["dsr"] = round(v, 4)
                        t["hold"] = H
                        surv.append(t)
                    nD += okH
                row["stageC"], row["stageD"] = nC, nD
            rows.append(row)
        out[lab] = {"families": F, "stageA": R, "stageB": sum(r.get("stageB", 0) for r in rows),
                    "stageC": sum(r.get("stageC", 0) for r in rows), "stageD": sum(r.get("stageD", 0) for r in rows),
                    "table": sorted(rows, key=lambda r: r["simes_p"]), "survivors": surv}
    return out


def confirm_track(X, say):
    """DESIGN_v3 pre-designated track: the 1h VWAP +-2sd momentum NY PM family, hold-outs spent once."""
    import grammar as G
    XX = X["1h"]
    fam = [I for I in G.ideas() if I["id"].startswith(CONFIRM_FAMILY)]
    per = {h: [] for h in HOLD}
    named = None
    for I in fam:
        d, r, g = G.run_idea(XX, I)
        H = {h: span_stats(d, r, XX, sp) for h, sp in HOLD.items()}
        if I["id"] == CONFIRM_NAMED:
            named = H
        for h in HOLD:
            if H[h]["n"]:
                per[h].append(H[h]["mean_r"])
    c1 = all(named[h]["n"] >= MIN_HOLD and (named[h]["mean_r"] or 0) > 0 and (named[h]["pf"] or 0) >= PF_HOLD for h in HOLD)
    avg = {h: round(float(np.mean(v)), 4) if v else None for h, v in per.items()}
    c2 = all((avg[h] or 0) > 0 for h in HOLD)
    res = {"family": CONFIRM_FAMILY, "named": CONFIRM_NAMED, "C1_named": named, "C1_pass": bool(c1),
           "C2_family_avg_r": avg, "C2_pass": bool(c2), "verdict": "paper" if (c1 and c2) else "rejected"}
    say(f"confirmation track {CONFIRM_FAMILY}: C1 {c1} {json.dumps(named)} | C2 {c2} {avg} -> {res['verdict']}")
    return res


# ================================================================================================ batch
def batch(n, cap_s=1200, say=print, journal=None):
    import grammar as G
    t0 = time.time()
    X = {tf: G.context(tf) for tf in G.TFS}
    data_end = str(X["5m"]["udays"][-1])
    T0 = load_trials()
    tried = {(t["id"], t["data_end"]) for t in T0 if t.get("proto") == PROTO}
    todo = [I for I in G.ideas() if (I["id"], data_end) not in tried]
    if n:
        todo = todo[:n]
    say(f"grammar ideas {sum(1 for _ in G.ideas())}, not tried on data to {data_end}: {len(todo)}")
    k = len(T0)
    done = 0
    import gzip
    with gzip.open(TRIALS, "at", encoding="utf-8") as fh:        # every trial written as it is scored: no silent drops
        for I in todo:
            if time.time() - t0 > cap_s:
                say(f"time cap reached after {done} ideas")
                break
            row = score_one(X[I["tf"]], I, data_end)
            k += 1; done += 1
            row["n"] = k
            fh.write(json.dumps(row, default=float) + "\n")
            if done % 1000 == 0:
                fh.flush(); say(f"  {done} scored [{time.time() - t0:.0f}s]")
    T_all = [t for t in load_trials() if t.get("proto") == PROTO]
    counts = gates(T_all, X, say)                     # v2-style flat BH, kept for comparison
    H3 = hier(T_all, X, say)
    counts.update({"v3_families": H3["real"]["families"], "v3_stageA": H3["real"]["stageA"], "v3_stageB": H3["real"]["stageB"],
                   "v3_stageC": H3["real"]["stageC"], "v3_stageD": H3["real"]["stageD"],
                   "v3_placebo": [H3["placebo"][k] for k in ("stageA", "stageB", "stageC", "stageD")]})
    confirm = confirm_track(X, say) if not os.path.exists(os.path.join(OUT, "confirm_v3.json")) else \
        json.load(open(os.path.join(OUT, "confirm_v3.json"), encoding="utf-8"))
    json.dump(confirm, open(os.path.join(OUT, "confirm_v3.json"), "w", encoding="utf-8"), indent=1, default=float)
    counts["confirm_track"] = confirm["verdict"]
    counts["tested_this_run"] = done
    counts["seconds"] = round(time.time() - t0)
    surv = sorted([t for t in T_all if t.get("gate") in ("G2", "G3")], key=lambda t: -(t["disc"].get("sr") or 0))
    g1 = sorted([t for t in T_all if t.get("gate") in ("G1", "G2", "G3")], key=lambda t: t["disc"]["p"])
    top = [{"id": t["id"], "gate": t["gate"], "disc": t["disc"], "hold": t.get("hold")} for t in (surv or g1)[:25]]
    best_raw = sorted([t for t in T_all if t.get("status") == "scored" and (t["disc"]["mean_r"] or 0) > 0],
                      key=lambda t: t["disc"]["p"])[:10]
    S = {"made": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "data_end": data_end, "design": "research/ideamill/DESIGN.md",
         "counts": counts, "families": H3["real"]["table"], "placebo_families": H3["placebo"]["table"][:10],
         "v3_survivors": [{"id": t["id"], "gate": t["gate"], "disc": t["disc"], "hold": t.get("hold")} for t in H3["real"]["survivors"]],
         "confirm_track": confirm, "top": top, "best_raw_p": [{"id": t["id"], "disc": t["disc"]} for t in best_raw], "week": week_counts(T_all)}
    S["of"] = of_grammar(say)                         # day-ofmax: the order-flow ideas, forward-only protocol (off until the data)
    json.dump(S, open(SUMMARY, "w", encoding="utf-8"), indent=1, default=float)
    to_journal(T_all, counts, journal)
    say(f"tested {done} | total trials {counts['trials_total']} | scored {counts['scored']} | too few {counts['too_few']} | "
        f"untestable {counts['untestable']} | mean>0 {counts['discovery_mean_positive']} | raw p<.05 {counts['raw_p_below_0.05']} "
        f"(luck ~{counts['expected_raw_p05_by_luck']:.0f}) | G1 BH {counts['G1_bh']} | G2 DSR {counts['G2_dsr']} | G3 hold-outs {counts['G3_holdouts']} | "
        f"placebo G1/G2/G3 {counts['placebo_G1']}/{counts['placebo_G2']}/{counts['placebo_G3']} | v3 families A/B/C/D "
        f"{counts['v3_stageA']}/{counts['v3_stageB']}/{counts['v3_stageC']}/{counts['v3_stageD']} of {counts['v3_families']} "
        f"(placebo {counts['v3_placebo']}) | confirm {counts['confirm_track']} | {counts['seconds']} s")
    return S


def week_counts(T_all):
    today = dt.date.today()
    wk = today - dt.timedelta(days=today.weekday())
    this = [t for t in T_all if t.get("t", "")[:10] >= wk.isoformat()]
    return {"week_from": wk.isoformat(), "tested_this_week": len(this), "tested_total": len(T_all),
            "survived_total": sum(1 for t in T_all if t.get("gate") in ("G2", "G3", "C", "D"))}


def to_journal(T_all, counts, path=None):
    """Survivors -> the Brain's journal (research/learn/journal.json): G2 watching, G3 paper (G4 needs-owner-yes later)."""
    try:
        from engine import market_learn as ML
    except Exception:  # noqa: BLE001
        return
    obs = [{"key": "ideamill|summary", "pillar": "market", "lens": "idea mill",
            "noticed": (f"idea mill: {counts['trials_total']} ideas tested so far; {counts['G1_bh']} passed discovery (FDR), "
                        f"{counts['G2_dsr']} the many-tests haircut, {counts['G3_holdouts']} all 3 hold-outs; a random-sign placebo "
                        f"gives {counts['placebo_G1']} / {counts['placebo_G2']} / {counts['placebo_G3']}"),
            "evidence": {"n": counts["trials_total"]}, "status": "watching"}]
    if "v3_stageA" in counts:
        obs[0]["noticed"] += (f"; family-first (v3): {counts['v3_stageA']} of {counts['v3_families']} families passed, "
                              f"{counts['v3_stageD']} variants survived the hold-outs")
    cf = counts.get("confirm_track")
    if cf:
        obs.append({"key": "ideamill|confirm|1h vwap momentum", "pillar": "market", "lens": "idea mill",
                    "noticed": "the 1h VWAP +-2sd momentum NY-afternoon family (the v2 discovery lead), confirmed on the 3 hold-outs: "
                               + ("PASSED -> forward paper" if cf == "paper" else "FAILED"),
                    "evidence": {}, "status": "paper" if cf == "paper" else "rejected"})
    for t in T_all:
        if t.get("gate") not in ("G2", "G3", "C", "D"):
            continue
        H = t.get("hold") or {}
        hw = "; ".join(f"{h} {H[h]['mean_r']}R x{H[h]['n']}" for h in H) if H else ""
        obs.append({"key": f"ideamill|{t['id']}", "pillar": "market", "lens": "idea mill",
                    "noticed": f"idea {t['id']}: discovery {t['disc']['mean_r']}R a trade over {t['disc']['n']} trades (p {t['disc']['p']}, "
                               f"DSR {t['disc'].get('dsr')}); hold-outs: {hw}",
                    "evidence": {"n": t["disc"]["n"], "z": t["disc"].get("sr")},
                    "status": "paper" if t["gate"] in ("G3", "D") else "watching"})
    path = path or ML.JOURNAL
    J, _ = ML.update_journal(ML.journal_doc(path), obs)
    ML._write_json(path, J)


# ================================================================================================ harvest
FAMILY = [("momentum|trend[- ]following|time[- ]series momentum", ["or_break", "pd_break", "ema_cross", "displacement"]),
          ("reversal|mean[- ]reversion|overreaction|contrarian", ["pd_sweep", "vwap_band", "rsi_rev", "on_sweep"]),
          ("overnight|intraday|close[- ]to[- ]open|open[- ]to[- ]close", ["gap", "on_sweep"]),
          ("opening range|first (half )?hour|market open", ["or_break", "nr7_or_break"]),
          ("moving average", ["ema_cross"]), ("vwap|volume[- ]weighted", ["vwap_cross", "vwap_band"]),
          ("volume|order flow|liquidity", ["vol_spike"]), ("volatility|vix|implied vol", ["displacement"]),
          ("gap", ["gap"]), ("calendar|day[- ]of[- ]the[- ]week|turn[- ]of[- ]the[- ]month|seasonal", []),
          ("gamma|dealer|option[s]? (market )?mak", [])]
FEEDS = ["https://export.arxiv.org/api/query?search_query=cat:q-fin.TR+OR+cat:q-fin.ST+OR+cat:q-fin.PM+OR+cat:q-fin.CP"
         "&sortBy=submittedDate&sortOrder=descending&max_results=150",
         "https://www.nber.org/rss/new.xml"]


def harvest(say=print):
    import urllib.request
    import xml.etree.ElementTree as ET
    papers = []
    for url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-idea-mill/1.0"})
            raw = urllib.request.urlopen(req, timeout=30).read()
            root = ET.fromstring(raw)
        except Exception as ex:  # noqa: BLE001
            say(f"harvest: {url.split('/')[2]} failed ({ex.__class__.__name__})")
            continue
        for e in root.iter():
            tag = e.tag.split("}")[-1]
            if tag not in ("entry", "item"):
                continue
            get = lambda k: next((x.text or "" for x in e if x.tag.split("}")[-1] == k), "")  # noqa: E731
            papers.append({"src": url.split("/")[2], "title": " ".join(get("title").split()),
                           "abstract": " ".join((get("summary") or get("description")).split())[:1500],
                           "link": get("id") or get("link"), "date": (get("published") or get("pubDate"))[:16]})
    mapped, human = [], []
    for p in papers:
        txt = (p["title"] + " " + p["abstract"]).lower()
        fam = [(pat, trig) for pat, trig in FAMILY if re.search(pat, txt)]
        futures = bool(re.search(r"futures|index|s&p|nasdaq|equity|stock", txt))
        if fam and any(t for _, t in fam) and futures:
            mapped.append({**p, "families": [f[0].split("|")[0] for f in fam], "grammar_triggers": sorted({x for _, t in fam for x in t})})
        elif fam or futures:
            human.append({**p, "why": "a trading idea the grammar cannot express yet (needs a human read)"})
    old = json.load(open(os.path.join(OUT, "harvest.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "harvest.json")) else {"papers": []}
    seen = {x["link"] for x in old.get("papers", [])}
    keep = old.get("papers", []) + [m for m in mapped if m["link"] not in seen]
    json.dump({"made": dt.date.today().isoformat(), "papers": keep}, open(os.path.join(OUT, "harvest.json"), "w", encoding="utf-8"), indent=1)
    oh = json.load(open(os.path.join(OUT, "needs_human.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "needs_human.json")) else []
    hs = {x["link"] for x in oh}
    json.dump(oh + [h for h in human if h["link"] not in hs], open(os.path.join(OUT, "needs_human.json"), "w", encoding="utf-8"), indent=1)
    say(f"harvest: {len(papers)} abstracts read, {len(mapped)} map to grammar families, {len(human)} need a human read")
    return {"read": len(papers), "mapped": len(mapped), "human": len(human)}


def rejected_registry(say=print):
    """docs/TESTED_AND_REJECTED.md entries with their dates; 'due' when the data grew >= 60 sessions past that date."""
    txt = open(os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md"), encoding="utf-8").read()
    import grammar as G  # noqa: F401
    import pandas as pd
    d5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1d.csv"))
    days = sorted(pd.to_datetime(d5["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d"))
    out = []
    for m in re.finditer(r"^- \*\*(.+?)\*\*", txt, flags=re.M):
        title = m.group(1)
        dm = re.search(r"(20\d\d-\d\d-\d\d)", title)
        if not dm:
            continue
        since = sum(1 for d in days if d > dm.group(1))
        out.append({"idea": title[:160], "date": dm.group(1), "sessions_since": since, "due": since >= 60})
    json.dump(out, open(os.path.join(OUT, "rejected_registry.json"), "w", encoding="utf-8"), indent=1)
    say(f"rejected registry: {len(out)} dated entries, {sum(o['due'] for o in out)} due for a re-run on new data")
    return out


def of_grammar(say=print) -> dict:
    """The `of` grammar (research/orderflow/DESIGN_forward.md): order-flow ideas have no 2021-24 discovery span, so they run under
    their own forward-only protocol (of_forward.run) on the PC's order-flow summaries; it switches itself on at 60 tick days.
    Never raises into the batch."""
    try:
        import importlib.util
        p = os.path.join(ROOT, "research", "orderflow", "of_forward.py")
        sp = importlib.util.spec_from_file_location("of_forward", p)
        m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        return m.run(say=say)
    except Exception as e:  # noqa: BLE001
        say(f"of grammar skipped: {e.__class__.__name__}: {str(e)[:120]}")
        return {"state": "error", "why": f"{e.__class__.__name__}: {str(e)[:120]}"}


def report(say=print):
    S = json.load(open(SUMMARY, encoding="utf-8")) if os.path.exists(SUMMARY) else {}
    say(json.dumps(S.get("counts"), indent=1))
    for t in S.get("top", [])[:10]:
        say(f"  {t['gate']} {t['id']} disc {t['disc']['mean_r']}R n{t['disc']['n']} p {t['disc']['p']} DSR {t['disc'].get('dsr')} "
            f"hold {json.dumps(t.get('hold'))}")
    return S


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--cap", type=float, default=20, help="minutes")
    ap.add_argument("--harvest", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--of", action="store_true", help="the order-flow grammar only (forward-only protocol)")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    if a.of:
        r = of_grammar()
        if os.path.exists(SUMMARY):                    # keep the batch's summary, refresh its "of" block
            S = json.load(open(SUMMARY, encoding="utf-8"))
            S["of"] = r
            json.dump(S, open(SUMMARY, "w", encoding="utf-8"), indent=1, default=float)
        return 0
    if a.harvest:
        harvest(); rejected_registry()
    if a.batch is not None:
        batch(a.batch, cap_s=a.cap * 60)
    if a.report or (a.batch is None and not a.harvest):
        report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
