"""Re-test under new standards (2026-11-23): regenerate PER-TRADE results of the stand-alone hunts whose JSON kept only
summaries. Calls each tool's own signal + execution code unchanged (futures data only, costs in), books every trade at
the hunts' common $500 risk (q = min(40, 500 // (risk*$2 + $1.90)), $1.90 a micro round trip, 1 tick fills per the
tool). Writes research/retest/cells_<src>.json (gitignored scratch).  PAPER ONLY.
    python -X utf8 tools/retest/regen.py <src>      src in third, hunt, plus, e2, div, pub
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")]
OUT = os.path.join(ROOT, "research", "retest")
PV, COMM = 2.0, 1.90


def bk(day, et, xt, d, risk, pts, w1):
    q = min(40, int(500.0 // (risk * PV + COMM))) if risk and risk > 0 else 0
    if q < 1:
        return None
    return [day, int(et), int(xt), int(d), round(float(risk), 3), round(float(pts), 3), round(float(min(0.0, w1)), 3),
            round(q * (pts * PV - COMM), 2)]


def third():
    import third_strategy as TS
    b = TS.B(); out = {}
    for cid, fam, cfg in TS.grid():
        rows = []
        for w in TS.execute(TS.FAM[fam](cfg)):
            e0 = w["i"] + 1; j = min(e0 + w["bars"], len(b.t) - 1)
            r = bk(w["day"], b.t[e0], b.t[j] + 300, w["dir"], w["risk"], w["pts"], -w["mae"] * w["risk"])
            if r: rows.append(r)
        out[f"third:{fam}:{cid}"] = rows
    return out


def _ds_rows(W):
    import div_search as DS
    return [[t["day"], t["entry_t"], t["exit_t"], t["dir"], t["risk_pts"], t["pts"], t["w1"], t["pnl"]] for t in DS.booked(W)]


def hunt():
    import new_hunt as NH
    return {f"hunt:{fam}:{cid}": _ds_rows(NH.execute(NH.FAM[fam](cfg))) for cid, fam, cfg in NH.grid()}


def e2():
    import e2_new_strats as E2
    return {f"e2:{cfg['fam']}:{cid}": _ds_rows(E2.run(cfg)) for cid, cfg in E2.grid()}


def div():
    import div_search as DS
    G = DS.na_grid() + DS.re_grid() + DS.ib_grid()
    return {f"div:{cfg['fam']}:{cid}": _ds_rows(DS.run(cfg)) for cid, cfg in G}


def plus():
    import atlas_plus as AP
    out = {}
    for cid, fam, cfg, tg in AP.grid():
        U = AP.execute(AP.FAM[fam](cfg), fam, tg)
        out[f"plus:{fam}:{cid}"] = [r for r in (bk(u["day"], u["entry_t"], u["exit_t"], u["dir"], u["risk"], u["pts"], u["w1"]) for u in U) if r]
    return out


def pub():
    sys.argv = [sys.argv[0], "x"]                   # pub_strats runs main() only with no argv
    import pub_strats as PS
    bars = {"NQ": PS.Strat(PS.Bars("NQ"), "NQ"), "ES": PS.Strat(PS.Bars("ES"), "ES")}
    out = {}
    for cid, sym, fn, mode, legal in PS.CELLS:
        if not legal:                                # overnight holds are not MFFU-legal: still listed, flagged
            pass
        T = fn(bars[sym], mode)
        rows = []
        for t in T:
            for s, u in t["legs"]:
                rows.append([s, 0, 0, t["d"], None, None, None, round(u, 2)])
        out[f"pub:{'day' if legal else 'overnight'}:{cid}"] = rows
    return out


if __name__ == "__main__":
    src = sys.argv[1]; t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    o = globals()[src]()
    json.dump(o, open(os.path.join(OUT, f"cells_{src}.json"), "w"), separators=(",", ":"))
    print(src, len(o), "cells", sum(len(v) for v in o.values()), "trades", round(time.time() - t0), "s")
