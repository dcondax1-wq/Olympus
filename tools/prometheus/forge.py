"""PROMETHEUS forge: evolve LIT knobs on 2026 H1, check the hall of fame on 2026 H2 and 2021-25, store the runs, write the
page data. Research only: never edits live_model*.json (a proposal goes in research/writeups/2026-11-03-prometheus.md).

    python -X utf8 -m tools.prometheus.forge                 # 5 seeds x 24 creatures x 20 generations, checks, runs, page
    python -X utf8 -m tools.prometheus.forge --quick         # smoke: 1 seed, 8 creatures, 3 generations, no runs stored
    python -X utf8 -m tools.prometheus.forge --no-runs       # everything but rl.save

Outputs
  research/prometheus/forge_results.json    every seed's champion, the hall of fame with H1 / H2 / 2021-25, the honesty stats
  tools/web_public/prometheus/forge.json    the page data (primary seed's generations, lineage, checks; <= 1 MB)
  tools/web_public/prometheus/jarvis.json   the Jarvis card (docs/JARVIS_APPS.md)
  research/runs/prometheus_*.json           tools/runlib.py runs (LIT size rule, every session, costs in)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.prometheus import fitness as FT  # noqa: E402
from tools.prometheus import ga as GA  # noqa: E402
from tools.prometheus import genome as G  # noqa: E402

OUT_DIR = os.path.join(ROOT, "research", "prometheus")
PAGE_DIR = os.path.join(ROOT, "tools", "web_public", "prometheus")
SEEDS = (7, 11, 23, 42, 101)          # 7 = the primary run shown on the page
MAX_PAGE_BYTES = 1_000_000
THEME = "#120806"
REAL_MARGIN_PCT = 10.0                # "a real margin" on H2: +10% $ per month, a bootstrap 5th percentile above 0, eval speed not worse


# ------------------------------------------------------------------------------------------------ honesty statistics
def spearman(a, b) -> float | None:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.all(a == a[0]) or np.all(b == b[0]):
        return None
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return round(float(np.corrcoef(ra, rb)[0, 1]), 3)


def block_bootstrap_pm(days_a, days_b, n=4000, block=5, seed=7) -> dict:
    """Weekly-block bootstrap of the $ per month difference a - b over the same sessions (daily P&L lists [[date, pnl]])."""
    da = {d: p for d, p in days_a}
    diff = np.array([da.get(d, 0.0) - p for d, p in days_b])
    if not len(diff):
        return {"pm": 0, "lo5": 0, "hi95": 0, "p_le0": 1.0}
    rng = np.random.default_rng(seed)
    nb = int(math.ceil(len(diff) / block))
    starts = np.arange(0, max(1, len(diff) - block + 1))
    sims = np.empty(n)
    for i in range(n):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.choice(starts, nb)])[:len(diff)]
        sims[i] = diff[idx].sum() / (len(diff) / 21)
    return {"pm": round(float(diff.sum() / (len(diff) / 21))), "lo5": round(float(np.percentile(sims, 5))),
            "hi95": round(float(np.percentile(sims, 95))), "p_le0": round(float((sims <= 0).mean()), 3)}


def h2_fit(c, live) -> float:
    """The same fitness formula on H2 numbers, scaled by live's H2 numbers (honesty: does the H1 ranking survive?)."""
    return FT.score({"pm": c["pm"], "p10": c["p10"], "f10": c["f10"], "tpw": c["tpw"]},
                    {"pm": live["pm"], "p10": live["p10"], "f10": live["f10"]})


def project(genomes) -> dict:
    """2D map of the genomes (PCA of the knob values scaled to 0..1) for the arena: {key: [x, y]} in -1..1."""
    X = np.array([[i / max(1, k.n - 1) for k, i in zip(G.KNOBS, g)] for g in genomes], float)
    mu = X.mean(0)
    Xc = X - mu
    if len(X) < 3 or not np.any(Xc):
        return {G.key(g): [0.0, 0.0] for g in genomes}
    _, _, vt = np.linalg.svd(Xc, full_matrices=False)
    P = Xc @ vt[:2].T
    for j in range(2):                       # a stable sign: the live genome on the negative side of each axis
        if P[0, j] > 0:
            P[:, j] *= -1
    P /= (np.abs(P).max(0) + 1e-9)
    return {G.key(g): [round(float(x), 3), round(float(y), 3)] for g, (x, y) in zip(genomes, P)}


# ------------------------------------------------------------------------------------------------ the forge
def evolve_seeds(fit, seeds, cfg_kw):
    runs = {}
    for s in seeds:
        t0 = time.time()
        hist = GA.evolve(fit, [k.n for k in G.KNOBS], G.live_genome(), GA.GAConfig(seed=s, **cfg_kw))
        fit.save()
        ch = GA.champion(hist)
        runs[s] = hist
        print(f"seed {s}: champion #{ch.id} gen {ch.gen} fit {ch.fit:.3f} H1 ${ch.metrics['pm']:,}/mo "
              f"p10/f10 {ch.metrics['p10']}/{ch.metrics['f10']} tpw {ch.metrics['tpw']} | {time.time() - t0:.0f}s, "
              f"{fit.calls} new evaluations so far", flush=True)
    return runs


def _slim(m, keys=("n", "tpw", "wk2", "win", "pf", "net", "pm", "dd", "p10", "f10", "p20", "f20", "pass_med", "lit_p10",
                   "lit_f10", "net_x3")):
    return {k: m[k] for k in keys if k in m}


def verdict(champ_chk, live_chk, boot) -> dict:
    l1, l2, c1, c2 = live_chk["H1"], live_chk["H2"], champ_chk["H1"], champ_chk["H2"]
    d1, d2 = c1["pm"] - l1["pm"], c2["pm"] - l2["pm"]
    surv = round(100 * d2 / d1, 1) if d1 > 0 else None
    sp_live, sp_ch = l2["p10"] - l2["f10"], c2["p10"] - c2["f10"]
    real = (d2 >= REAL_MARGIN_PCT / 100 * abs(l2["pm"]) and boot["lo5"] > 0 and sp_ch >= sp_live and c2["tpw"] >= 2.0)
    return {"h1_gain_pm": d1, "h2_gain_pm": d2, "survive_pct": surv, "h2_speed_live": round(sp_live, 1),
            "h2_speed_champ": round(sp_ch, 1), "boot": boot, "real_margin": bool(real),
            "y_gain_pm": champ_chk["2021-25"]["pm"] - live_chk["2021-25"]["pm"]}


def build(seeds=SEEDS, cfg_kw=None, store_runs=True, page=True, quick=False):
    cfg_kw = cfg_kw or {}
    t0 = time.time()
    fit = FT.Fitness(persist=not quick)
    live_g = G.live_genome()
    print("live H1:", fit.ref, flush=True)
    runs = evolve_seeds(fit, seeds, cfg_kw)
    primary = seeds[0]
    hist = runs[primary]
    champ = GA.champion(hist)
    line, ancestors = GA.lineage(hist, champ.id)
    hof = GA.hall_of_fame(hist, 10)

    # ---- checks: every distinct genome of the primary run (cheap), full checks for live + hall of fame + seed champions
    genomes = []
    for c in [cc for gen in hist for cc in gen]:
        if c.genome not in genomes:
            genomes.append(c.genome)
    seed_champs = {s: GA.champion(h) for s, h in runs.items()}
    full_set = [live_g] + [c.genome for c in hof] + [c.genome for c in seed_champs.values()]
    print(f"checking {len(genomes)} distinct genomes on H2 / 2021-25 ...", flush=True)
    checks = {}
    for g in genomes:
        checks[G.key(g)] = FT.check(g)
    full = {}
    for g in full_set:
        if G.key(g) not in full:
            full[G.key(g)] = FT.check(g, full=True)
            checks[G.key(g)] = {k: v for k, v in full[G.key(g)].items() if not k.startswith("_")}
    lk = G.key(live_g)
    live_chk = full[lk]
    for k, v in checks.items():                  # the check's H1 (one run over every session) = the fitness's H1-only run
        h = fit.cache[k]
        assert (v["H1"]["n"], v["H1"]["net"], v["H1"]["p10"]) == (h["n"], h["net"], h["p10"]), (k, v["H1"], h)

    # ---- honesty
    fit1 = [score_h1 for score_h1 in (FT.score(fit.cache[G.key(g)], fit.ref) for g in genomes)]
    fit2 = [h2_fit(checks[G.key(g)]["H2"], live_chk["H2"]) for g in genomes]
    rho = spearman(fit1, fit2)
    boots = {}
    for s, c in seed_champs.items():
        ck = full[G.key(c.genome)]
        boots[s] = block_bootstrap_pm([d for d in ck["H2"]["_days"]], live_chk["H2"]["_days"])
    V = {s: verdict(full[G.key(c.genome)], live_chk, boots[s]) for s, c in seed_champs.items()}
    best_h2 = max(genomes, key=lambda g: checks[G.key(g)]["H2"]["pm"])

    res = {
        "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "seeds": list(seeds), "primary": primary,
        "ga": {**GA.GAConfig(**cfg_kw).__dict__, "seed": primary}, "knobs": G.spec(),
        "fitness": {"formula": "0.5 x $/mo / live $/mo + 0.5 x (p10 - f10) / live (p10 - f10) - 0.5 x (2 - trades/wk)+ - 0.25 x (trades/wk - 4)+",
                    "span": "2026-01-02 .. 2026-06-30 only", "live_h1": _slim(fit.ref), "evaluations": len(fit.cache)},
        "live": {"values": G.values(live_g), "H1": _slim(live_chk["H1"]), "H2": _slim(live_chk["H2"]), "2021-25": _slim(live_chk["2021-25"])},
        "seed_champions": [{"seed": s, "id": c.id, "gen": c.gen, "fit": c.fit, "values": G.values(c.genome), "diff": G.diff(c.genome),
                            **{sp: _slim(full[G.key(c.genome)][sp]) for sp in ("H1", "H2", "2021-25")}, "verdict": V[s]}
                           for s, c in seed_champs.items()],
        "hall_of_fame": [{"id": c.id, "gen": c.gen, "fit": c.fit, "values": G.values(c.genome), "diff": G.diff(c.genome),
                          "h2_fit": h2_fit(full[G.key(c.genome)]["H2"], live_chk["H2"]),
                          **{sp: _slim(full[G.key(c.genome)][sp]) for sp in ("H1", "H2", "2021-25")}} for c in hof],
        "honesty": {"spearman_h1_h2_fit": rho, "genomes_checked": len(genomes),
                    "beat_live_h1": sum(1 for f in fit1 if f > 1.0), "beat_live_h2": sum(1 for f in fit2 if f > h2_fit(live_chk["H2"], live_chk["H2"])),
                    "beat_live_both": sum(1 for a, b in zip(fit1, fit2) if a > 1.0 and b > 1.0),
                    "spearman_h1_h2_pm": spearman([fit.cache[G.key(g)]["pm"] for g in genomes], [checks[G.key(g)]["H2"]["pm"] for g in genomes]),
                    "beat_live_h1_pm": sum(1 for g in genomes if fit.cache[G.key(g)]["pm"] > fit.ref["pm"]),
                    "beat_live_h2_pm": sum(1 for g in genomes if checks[G.key(g)]["H2"]["pm"] > live_chk["H2"]["pm"]),
                    "beat_live_both_pm": sum(1 for g in genomes if fit.cache[G.key(g)]["pm"] > fit.ref["pm"]
                                             and checks[G.key(g)]["H2"]["pm"] > live_chk["H2"]["pm"]),
                    "best_h2_in_run": {"values": G.values(best_h2), "H1_fit": FT.score(fit.cache[G.key(best_h2)], fit.ref),
                                       "H2": _slim(checks[G.key(best_h2)]["H2"]),
                                       "note": "picked on H2 itself: shown for honesty, never a proposal"}},
        "seconds": round(time.time() - t0),
    }
    res["proposal"] = any(v["real_margin"] for v in V.values()) and V[primary]["real_margin"]
    if not quick:
        os.makedirs(OUT_DIR, exist_ok=True)
        _write(os.path.join(OUT_DIR, "forge_results.json"), res, indent=1)
    if store_runs:
        save_runs(seed_champs, full, live_chk, V, primary)
    if page:
        P = page_data(hist, champ, line, ancestors, checks, fit, live_g, res, genomes)
        write_page(P, res, quick)
    print(f"forge done in {time.time() - t0:.0f}s; primary champion verdict: {V[primary]}", flush=True)
    return res


def _write(path, obj, **kw):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, **kw)
    os.replace(tmp, path)


def save_runs(seed_champs, full, live_chk, V, primary):
    """tools/runlib.py runs of each seed's champion (LIT size rule, every session, costs in; run lit_live is the live one)."""
    from tools import lit_final as F
    from tools import runlib as rl
    from engine import lit
    for s, c in seed_champs.items():
        ck = full[G.key(c.genome)]
        T = [{k: v for k, v in t.items() if not k.startswith("_") and k not in ("size_why", "size_mult")} for t in ck["_trades"]]
        v = V[s]
        h = lambda x: (f"n={x['n']} {x['tpw']}/wk PF {x['pf']} net {x['net']:+,} (${x['pm']:,}/mo) DD {x['dd']:,}"  # noqa: E731
                       + (f" eval path 2-week pass/fail {x['p10']}/{x['f10']}" if "p10" in x else ""))
        lv = live_chk
        rl.save(f"prometheus_s{s}", f"PROMETHEUS champion (seed {s}): " + ", ".join(f"{k} {a}->{b}" for k, (a, b) in G.diff(c.genome).items()),
                "other", "Can a genetic algorithm on 2026 H1 find LIT knob values that also beat the live ones on 2026 H2?",
                params={**lit.DEFAULTS, **G.lit_params(c.genome), "room_f": G.values(c.genome)["room_f"]}, trades=T,
                scored=rl.score(T, F.SESS),
                status="promising" if v["real_margin"] else "rejected",
                verdict=(f"Picked on 2026 H1 by the GA (seed {s}, fitness {c.fit:.3f}, live = 1.0). H1 {h(ck['H1'])} vs live "
                         f"{h(lv['H1'])}; H2 (check) {h(ck['H2'])} vs live {h(lv['H2'])}; 2021-25 reference {h(ck['2021-25'])} vs "
                         f"live {h(lv['2021-25'])}. H2 gain ${v['h2_gain_pm']:+,}/mo (bootstrap 5-95% ${v['boot']['lo5']:+,}.."
                         f"${v['boot']['hi95']:+,}); real margin: {'yes' if v['real_margin'] else 'no'}."),
                notes="tools/prometheus/forge.py: engine/lit.py run_x via tools/lit_final.run on live_model_lit.json + the genome; "
                      "eval path = tools/lit_adv_manage.run_eval with the genome's room_f. room_f acts on the eval path only.",
                writeup="2026-11-03-prometheus", tags=["lit", "prometheus"])
        print(f"saved run prometheus_s{s}", flush=True)


# ------------------------------------------------------------------------------------------------ page data
def page_data(hist, champ, line, ancestors, checks, fit, live_g, res, genomes):
    xy = project([live_g] + [g for g in genomes if g != live_g])
    gk = {}
    for g in genomes:
        k = G.key(g)
        c = checks[k]
        gk[k] = {"v": [int(i) for i in g], "xy": xy[k],
                 "h1": _slim(c["H1"], ("n", "tpw", "pf", "net", "pm", "dd", "p10", "f10", "wk2")),
                 "h2": _slim(c["H2"], ("n", "tpw", "pf", "net", "pm", "dd", "p10", "f10", "wk2")),
                 "y": _slim(c["2021-25"], ("n", "tpw", "pf", "net", "pm", "dd", "lit_p10", "lit_f10")),
                 "f2": h2_fit(c["H2"], checks[G.key(live_g)]["H2"])}
    ORG = {"live": "L", "spark": "S", "random": "R", "elite": "E", "child": "C"}
    gens = [[{"id": c.id, "k": G.key(c.genome), "f": round(c.fit, 4), "o": ORG[c.origin], "p": list(c.parents),
              "mu": list(c.mutated)} for c in gen] for gen in hist]
    V = next(x["verdict"] for x in res["seed_champions"] if x["seed"] == res["primary"])
    return {
        "v": 1, "app": "prometheus", "built": res["built"], "demo": False,
        "seed": res["primary"], "pop": len(hist[0]), "gens_n": len(hist),
        "knobs": G.spec(), "live": {"k": G.key(live_g), "fit": 1.0},
        "fitness": res["fitness"]["formula"],
        "genomes": gk, "gens": gens,
        "champion": {"id": champ.id, "k": G.key(champ.genome), "gen": champ.gen, "fit": round(champ.fit, 4),
                     "line": line, "ancestors": ancestors, "diff": G.diff(champ.genome)},
        "verdict": V, "honesty": {k: v for k, v in res["honesty"].items() if k != "best_h2_in_run"},
        "seeds": [{"seed": x["seed"], "fit": round(x["fit"], 3), "diff": x["diff"], "h1_pm": x["H1"]["pm"], "h2_pm": x["H2"]["pm"],
                   "h2_p10": x["H2"]["p10"], "h2_f10": x["H2"]["f10"], "y_pm": x["2021-25"]["pm"], "real": x["verdict"]["real_margin"]}
                  for x in res["seed_champions"]],
        "proposal": res["proposal"],
    }


def jarvis_card(P) -> dict:
    ch = P["genomes"][P["champion"]["k"]]
    lv = P["genomes"][P["live"]["k"]]
    V = P["verdict"]
    lvl = "warn" if P["proposal"] else "ok"          # warn = a candidate needs the owner's look; ok = live holds
    lab = "Forge: a candidate to review" if P["proposal"] else "Forge: live LIT holds on H2"
    money = lambda x: ("-" if x < 0 else "") + "$" + f"{abs(round(x)):,}"   # noqa: E731
    return {"v": 1, "name": "Prometheus", "status": {"level": lvl, "label": lab[:48]},
            "kpis": [{"label": "Champion H1 $/mo", "value": money(ch["h1"]["pm"]), "delta": f"{'+' if V['h1_gain_pm'] >= 0 else '-'}{money(abs(V['h1_gain_pm']))}"},
                     {"label": "Its H2 $/mo", "value": money(ch["h2"]["pm"]), "delta": f"{'+' if V['h2_gain_pm'] >= 0 else '-'}{money(abs(V['h2_gain_pm']))}"},
                     {"label": "Live H2 $/mo", "value": money(lv["h2"]["pm"])}],
            "lines": [f"{P['gens_n']} generations x {P['pop']} creatures, fitness on 2026 H1 only"[:120],
                      (f"H1 gain kept on H2: {V['survive_pct']}%" if V["survive_pct"] is not None else "No H1 gain over live")[:120],
                      ("Real margin on H2: yes, see the write-up" if P["proposal"] else "No real H2 margin: nothing to switch")[:120]],
            "t": int(time.time()), "open": "#forge", "theme": THEME}


def write_page(P, res, quick=False):
    s = json.dumps(P, separators=(",", ":"))
    assert len(s.encode()) <= MAX_PAGE_BYTES, f"forge.json {len(s)} bytes > 1 MB"
    if quick:
        print(f"(quick) page data {len(s):,} bytes, not written", flush=True)
        return
    os.makedirs(PAGE_DIR, exist_ok=True)
    with open(os.path.join(PAGE_DIR, "forge.json"), "w", encoding="utf-8") as fh:
        fh.write(s)
    _write(os.path.join(PAGE_DIR, "jarvis.json"), jarvis_card(P), separators=(",", ":"))
    print(f"page data {len(s):,} bytes -> tools/web_public/prometheus/forge.json", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-runs", action="store_true")
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    a = ap.parse_args(argv)
    seeds = tuple(int(x) for x in a.seeds.split(","))
    if a.quick:
        return build(seeds[:1], {"pop": 8, "gens": 3, "n_spark": 3}, store_runs=False, page=True, quick=True)
    return build(seeds, store_runs=not a.no_runs)


if __name__ == "__main__":
    main()
