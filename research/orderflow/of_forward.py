"""Order-flow ideas, forward-only protocol (research/orderflow/DESIGN_forward.md, frozen ab61ea293). Paper research only.

The idea mill's `of` grammar: tools/ideamill.py calls run() in every --batch (and --of). Off under 60 tick days, provisional
from 60, frozen split from 120 (research/ideamill/of_split.json, written once). 36 families = (entry, feature group; v2 A-H + v3 I-L, DESIGN3.md);
gates A (Simes + BH over families), B (BH inside at q R / F), C (deflated Sharpe), D (Confirm), E (20 Forward trades);
the placebo through the same gates.
    python -X utf8 research/orderflow/of_forward.py [--src DIR]      python -X utf8 research/orderflow/of_forward.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
OUTD = os.path.join(ROOT, "research", "ideamill")
SPLIT = os.path.join(OUTD, "of_split.json")
TRIALS = os.path.join(OUTD, "of_trials.jsonl")
OFF_UNDER, FREEZE_AT, DISC_FRAC = 60, 120, 0.60
Q, DSR_MIN, MIN_DISC, MIN_CONF, MIN_FWD, PF_CONF, N_PERM = 0.10, 0.95, 30, 10, 20, 1.10, 1000


def _mod(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


M = _mod("of_mill.py", "of_mill_f")         # features, entry_rows, Ctx, bh, dsr, FEATURES
B = M.B                                    # of_battery: Day, find_days, lit_trades, atlas_md
V3 = _mod("of_v3.py", "of_v3_f")           # day-oflearn: DESIGN3.md groups I / J / K / L join the families (L like G: depth)


def groups():
    g = {}
    for f in M.FEATURES:
        g.setdefault(f[0], []).append(f)
    for k, fs in V3.GROUPS_V3.items():                                      # DESIGN3: 24 + 12 = 36 families
        g[k] = list(fs)
    return g


def all_features(cx, i, d, ext_i, level):
    """v2 (DESIGN2) + v3 (DESIGN3) features of one entry row."""
    return {**M.features(cx, i, d, ext_i, level), **V3.features(cx, i, d, ext_i, level)}


def _perm_p(pnl, keep, alt, fam, rng):
    """One-sided permutation p of a variant on one span (filter: random skips of the same count; LVL: coin-flip)."""
    if fam == "LVL":
        act, flp = pnl[keep], alt[keep]
        if not len(act):
            return 1.0
        dr = np.array([np.where(rng.random(len(act)) < 0.5, act, flp).sum() for _ in range(N_PERM)])
        return float((dr >= act.sum()).mean())
    ns = int((~keep).sum())
    if not len(pnl) or ns in (0, len(pnl)):
        return 1.0
    obs = -pnl[~keep].sum()
    dr = np.array([-pnl[rng.choice(len(pnl), ns, replace=False)].sum() for _ in range(N_PERM)])
    return float((dr >= obs).mean())


def _span(pnl, keep, alt, fam, mask, rng, ndays):
    p, k, a = pnl[mask], keep[mask], alt[mask]
    if fam == "LVL":
        act = p[k]
        gain = float(act.sum())
        w, l = act[act > 0].sum(), -act[act <= 0].sum()
        pf = float(w / l) if l > 0 else (99.0 if w > 0 else 0.0)
    else:
        gain = float(-(p[~k]).sum())
        pf = None
    return {"n": int(k.sum()), "gain": round(gain), "p": round(_perm_p(p, k, a, fam, rng), 4), "pf": None if pf is None else round(pf, 2),
            "wk": round(int(k.sum()) / max(1, ndays) * 5, 2)}


def split_of(days, backfill_done=False):
    """(split_day, confirm_end, state) - frozen once in of_split.json."""
    try:
        fz = json.load(open(SPLIT, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        fz = None
    if fz:
        return fz["split_day"], fz["confirm_end"], "frozen"
    if len(days) < OFF_UNDER:
        return None, None, "off"
    k = int(round(DISC_FRAC * len(days))) - 1
    sd, ce = days[k], days[-1]
    if len(days) >= FREEZE_AT or backfill_done:
        os.makedirs(os.path.dirname(SPLIT), exist_ok=True)
        json.dump({"split_day": sd, "confirm_end": ce, "frozen_t": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   "days_at_freeze": len(days), "design": "research/orderflow/DESIGN_forward.md @ ab61ea293"}, open(SPLIT, "w"), indent=1)
        return sd, ce, "frozen"
    return sd, ce, "provisional"


def run(R=None, src=None, lit=None, atlas=None, say=print, write=True, backfill_done=False, seed=20261125):
    """The of grammar. Returns the block tools/ideamill.py puts in summary.json under "of"."""
    if R is None:
        R = B.find_days(src)
    days = sorted(d for d, x in R.items() if int(x["meta"].get("rows", 0)) >= B.MIN_ROWS)
    sd, ce, state = split_of(days, backfill_done)
    out = {"state": state, "tick_days": len(days), "design": "research/orderflow/DESIGN_forward.md"}
    if state == "off":
        out["why"] = f"waiting: {len(days)} of {OFF_UNDER} tick days (the battery covers 40-60)"
        say(f"of grammar: {out['why']}")
        return out
    disc = [d for d in days if d <= sd]
    conf = [d for d in days if sd < d <= ce]
    fwd = [d for d in days if d > ce]
    out.update(split_day=sd, confirm_end=ce, days={"discovery": len(disc), "confirm": len(conf), "forward": len(fwd)})
    D = {d: B.Day(d, R[d]) for d in days}
    if lit is None:
        lit, _ = B.lit_trades()
    if atlas is None:
        atlas, _ = B.atlas_md()
    ctx = {d: M.Ctx(D[d]) for d in days}
    rows = M.entry_rows(D, days, lit, atlas)
    F = [all_features(ctx[r[1]], r[2], r[3], r[6], r[7]) for r in rows]
    depth_days = sum(1 for d in days if getattr(D[d], "depth", None) is not None and len(D[d].depth))
    dset, cset, fset = set(disc), set(conf), set(fwd)
    G = groups()
    fams = []
    for fam in ("LIT", "ATLAS", "LVL"):
        idx = [k for k, r in enumerate(rows) if r[0] == fam]
        if not idx:
            continue
        pnl = np.array([rows[k][4] for k in idx], float)
        alt = np.array([rows[k][5] if rows[k][5] is not None else 0.0 for k in idx], float)
        day = np.array([rows[k][1] for k in idx])
        md, mc, mf = (np.array([x in S_ for x in day]) for S_ in (dset, cset, fset))
        for g, feats in G.items():
            if g in ("G", "L") and depth_days < 40:
                continue
            fr = {"family": f"{fam}|{g}", "variants": []}
            for feat in feats:
                vals = np.array([F[k][feat] for k in idx], float)
                fin = np.isfinite(vals)
                if (fin & md).sum() < MIN_DISC:
                    continue
                med = float(np.median(vals[fin & md]))
                for side in ("hi", "lo"):
                    keep = np.where(fin, vals >= med if side == "hi" else vals <= med, fam != "LVL")
                    vid = f"{fam}|{feat}|{side}"
                    rng = np.random.default_rng(zlib.crc32(vid.encode()) ^ seed)
                    pk = rng.permutation(keep) if fam != "LVL" else keep
                    pp = pnl if fam != "LVL" else np.where(rng.random(len(pnl)) < 0.5, pnl, alt)
                    v = {"id": vid, "median": round(med, 4)}
                    for lab, kk, pn in (("real", keep, pnl), ("placebo", pk, pp)):
                        v[lab] = {"disc": _span(pn, kk, alt, fam, md, rng, len(disc)), "conf": _span(pn, kk, alt, fam, mc, rng, len(conf)),
                                  "fwd": _span(pn, kk, alt, fam, mf, rng, len(fwd))}
                        dd = {d: 0.0 for d in disc}
                        for x, k_, dy in zip(pn, kk, day):
                            if k_ and dy in dd:
                                dd[dy] += x - (0.0 if fam == "LVL" else 0.0)
                        v[lab]["_daily"] = np.array([dd[d] for d in disc])
                    fr["variants"].append(v)
            if fr["variants"]:
                fams.append(fr)
    counts = {}
    for lab in ("real", "placebo"):
        fp = [M_simes([v[lab]["disc"]["p"] for v in f["variants"]]) for f in fams]
        okA = M.bh(fp, Q)
        Rn, Fn = int(okA.sum()), len(fams)
        c = {"families": Fn, "A": Rn, "B": 0, "C": 0, "D": 0, "E": 0}
        for f, a, p_ in zip(fams, okA, fp):
            f.setdefault("simes", {})[lab] = round(p_, 5)
            f.setdefault("stageA", {})[lab] = bool(a)
            if not a:
                continue
            okB = M.bh([v[lab]["disc"]["p"] for v in f["variants"]], Q * Rn / max(1, Fn))
            srs = [x.mean() / x.std(ddof=1) for x in (v[lab]["_daily"] for v in f["variants"]) if len(x) > 2 and x.std(ddof=1) > 0]
            var_sr = float(np.var(srs)) if len(srs) > 1 else 0.0
            for v, b_ in zip(f["variants"], okB):
                s = v[lab]
                fam_ = f["family"].split("|")[0]
                if not (b_ and s["disc"]["gain"] > 0 and s["disc"]["n"] >= MIN_DISC):
                    continue
                c["B"] += 1
                s["dsr"] = round(M.dsr(s["_daily"], len(f["variants"]), var_sr), 3)
                if s["dsr"] < DSR_MIN:
                    continue
                c["C"] += 1
                cf = s["conf"]
                if not (cf["gain"] > 0 and cf["n"] >= MIN_CONF and cf["p"] < 0.10 and (fam_ != "LVL" or (cf["pf"] or 0) >= PF_CONF)):
                    continue
                c["D"] += 1
                s["stage"] = "D: forward paper"
                fw = s["fwd"]
                if state == "frozen" and fw["n"] >= MIN_FWD and fw["gain"] > 0:
                    c["E"] += 1
                    s["stage"] = "E: needs-owner-yes"
        counts[lab] = c
    if state == "provisional":
        counts["real"]["E"] = 0
        out["note"] = "provisional split: a dry run of the gates, no candidate can come from it"
    surv = [{"id": v["id"], "stage": v["real"]["stage"], "disc": v["real"]["disc"], "conf": v["real"]["conf"], "fwd": v["real"]["fwd"],
             "dsr": v["real"].get("dsr")} for f in fams for v in f["variants"] if v["real"].get("stage")]
    out.update(counts=counts, depth_days=depth_days, survivors=surv,
               families=sorted([{"family": f["family"], "variants": len(f["variants"]), "simes_p": f["simes"]["real"],
                                 "stageA": f["stageA"]["real"]} for f in fams], key=lambda r: r["simes_p"])[:24])
    say(f"of grammar ({state}): {len(days)} tick days, discovery {len(disc)} / confirm {len(conf)} / forward {len(fwd)}; families "
        f"A/B/C/D/E {counts['real']['A']}/{counts['real']['B']}/{counts['real']['C']}/{counts['real']['D']}/{counts['real']['E']} of "
        f"{counts['real']['families']} (placebo {[counts['placebo'][k] for k in 'ABCDE']})")
    if write:
        os.makedirs(OUTD, exist_ok=True)
        with open(TRIALS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **{k: out[k] for k in
                                ("state", "tick_days", "split_day", "confirm_end", "days", "counts")}, "survivors": [s["id"] for s in surv]}) + "\n")
    return out


def M_simes(p):
    p = np.sort(np.asarray(p, float))
    m = len(p)
    return float(min(1.0, np.min(p * m / np.arange(1, m + 1)))) if m else 1.0


def selftest():
    """Synthetic days: a planted LIT signal (A1) must reach stage D; the placebo must not; the split freezes once."""
    global SPLIT, TRIALS
    import tempfile
    import pandas as pd
    from engine import ofsum
    with tempfile.TemporaryDirectory() as td:
        SPLIT, TRIALS = os.path.join(td, "of_split.json"), os.path.join(td, "of_trials.jsonl")
        days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-03-02", periods=130)]
        R, metas = {}, {}
        for k, d in enumerate(days):
            x = ofsum.synth_day(d, n=40_000, seed=k)
            R[d] = B._from_bytes(ofsum.summarize(x, d, ofsum.block_threshold(d, metas=metas)))
            R[d]["meta"]["rows"] = 60_000                           # synthetic days are small: count them as full days
            metas[d] = R[d]["meta"]
        D = {d: B.Day(d, R[d]) for d in days}
        rng = np.random.default_rng(9)
        lit = []
        for d in days:
            b = D[d].bars
            for _ in range(2):
                j = min(int(rng.integers(130, 180)), len(b) - 1)
                dd = int(rng.choice([-1, 1]))
                a1 = dd * b.delta.iloc[j - 1] / max(1, b.volume.iloc[j - 1])
                lit.append({"day": d, "dir": dd, "pnl": float((350 if a1 > 0 else -350) + rng.normal(0, 120)),
                            "te": int(b.t.iloc[j - 2]), "tn": int(b.t.iloc[j])})
        off = run({d: R[d] for d in days[:50]}, lit=lit, atlas=[], say=lambda *_: None, write=False)
        prov = run({d: R[d] for d in days[:80]}, lit=lit, atlas=[], say=lambda *_: None, write=False)
        out = run(R, lit=lit, atlas=[], say=print, write=True)
        fz = json.load(open(SPLIT))
        again = run(R, lit=lit, atlas=[], say=lambda *_: None, write=False)
        ids = {s["id"]: s["stage"] for s in out["survivors"]}
        ok = (off["state"] == "off" and prov["state"] == "provisional" and prov["counts"]["real"]["E"] == 0
              and out["state"] == "frozen" and fz["split_day"] == again["split_day"] == out["split_day"]
              and ids.get("LIT|A1|hi", "").startswith("D") and out["counts"]["placebo"]["D"] <= 1
              and out["days"]["forward"] == 0 and os.path.exists(TRIALS))
        print("of_forward selftest:", "OK" if ok else "FAIL", "| planted LIT|A1|hi:", ids.get("LIT|A1|hi"), "| real",
              out["counts"]["real"], "| placebo", out["counts"]["placebo"], "| split", fz["split_day"], fz["confirm_end"])
        return bool(ok)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    run(src=a.src)
