"""Structure management for ATLAS (account B: EMA + MACD + S/R on the MFFU Builder 25K), the companion of
tools/structure_manage.py (LIT). Judged the ATLAS way: 2026 (H1 picked / H2 check) AND 2021-25 (2025 + 2021-24), 2+ trades a
week, money + MFFU eval metrics from tools/atlas.score (the real account-B rules: need sizing on the 25K, LIT first, no
hedge, LIT's armed setups block, max 2 a day, $600 soft daily loss).

The member trades are the stored research trades (tools/second_mix.units = research/second/*_best.json). Their own
simulators run on other bar sets, so the change of a rule is measured by the DIFFERENCE method: one small executor
(engine/advisor.walk: stop before target, the member's breakeven / 15-minute check, flat 15:55) walks each trade on the
same bars twice, base and with the rule; the stored points get (rule - base) added, only when the rule fired. Bars: true 1m
in 2026 (days with full 1m coverage), 5m otherwise. Structure: engine/structure on the whole history (tools/structure_manage
.events), closed bars only.

Rules (X):
  choch   {"tf", "k", "act"}   a CHoCH against the trade once +k R -> exit at the next open / stop to entry + 1.25
  trail   {"tf", "k", "kinds"} after a break in favour once +k R, the stop to 1 tick beyond the new protected swing
  pstop   {"tf", "cap"}        the stop at the protected swing of tf at the entry (1 tick beyond it) when the tf trend is
                               with the trade and that swing sits beyond today's stop (wider, at most cap x the risk); size
                               follows the stop (account-B need sizing on the new risk); S/R keeps its 2R target in R, the
                               VIX targets keep their price. Measured fully on the executor (base = the executor's own base).

    python -X utf8 tools/structure_atlas.py check
    python -X utf8 tools/structure_atlas.py grid      # -> research/second/structure_atlas.json
    python -X utf8 tools/structure_atlas.py save
Paper research only.
"""
from __future__ import annotations

import collections
import copy
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import advisor as AD  # noqa: E402
from engine import structure as ST  # noqa: E402
from tools import atlas as A  # noqa: E402
from tools import second_mix as M  # noqa: E402
from tools import structure_manage as SM  # noqa: E402
from tools import lit_rev_exit as RX  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "structure_atlas.json")
TICK = 0.25
SRC = {"EMA": ("research/second/ema_best.json", "ema_lon_vix"), "MD": ("research/second/md_best.json", "macd_sweep"),
       "SR": ("research/second/sr_best.json", "sr_nyreclaim")}
SPECS = {"EMA": {"be_r": 1.0, "trail_r": None, "max_bars": None, "tcheck": None},
         "MD": {"be_r": None, "trail_r": None, "max_bars": None, "tcheck": (15, 0.3, 0.5)},
         "SR": {"be_r": None, "trail_r": None, "max_bars": None, "tcheck": (15, 0.3, 0.5)}}


def prices():
    """(src, entry_t, dir) -> the stored research trade with its prices."""
    out = {}
    for src, (p, _) in SRC.items():
        for t in json.load(open(os.path.join(ROOT, p)))["trades"]:
            out[(src, int(t["entry_t"]), int(t["dir"]))] = t
    return out


_RW: dict = {}


def rows_for(t):
    """1m rows of the trade's session from the fill on (2026 days with full 1m coverage), else 5m rows; the spec of the bars."""
    c = RX.cx()
    B1 = c[60].B
    day = t["day"]
    k = SM.day_k(day)
    use1 = k is not None and B1.full is not None and k in B1.full
    B = B1 if use1 else c[300].B
    i0 = int(np.searchsorted(B.t, int(t["entry_t"])))
    if i0 >= B.n:
        return None, None
    i1 = i0
    dk = B.day[i0]
    while i1 < B.n and B.day[i1] == dk:
        i1 += 1
    rows = np.column_stack([B.t[i0:i1], B.o[i0:i1], B.h[i0:i1], B.l[i0:i1], B.c[i0:i1]]).tolist()
    for r in rows:
        r[0] = int(r[0])
    return rows, (60 if use1 else 300)


def _walk_secs(rows, secs, d, entry, stop, target, spec, rule=None, ev=None):
    """engine/advisor.walk on 1m rows; on 5m rows the 15-minute check is 3 bars (as the research's 5m executors)."""
    sp = dict(spec)
    if secs == 300 and sp.get("tcheck"):
        sp["tcheck"] = (3, sp["tcheck"][1], sp["tcheck"][2])
    if secs == 300 and rule and rule.get("tf") == "1m":
        rule = {**rule, "tf": "5m"}
    return AD.walk(rows, 0, d, entry, stop, target, sp, rule, ev, secs=secs)


def pstop_at(t, tf, d, entry, stop, cap):
    """1 tick beyond the tf protected swing at the entry when the tf trend is with the trade and the swing is beyond the stop."""
    E = SM.events(tf)
    i = int(np.searchsorted(E["known_t"], int(t["entry_t"]), side="right")) - 1
    if i < 0 or int(E["dir"][i]) != d:
        return None
    prot = float(E["prot"][i])
    ns = prot - TICK if d == 1 else prot + TICK
    risk0 = (entry - stop) * d
    risk1 = (entry - ns) * d
    if risk1 <= risk0 + TICK or risk1 > cap * risk0:
        return None
    return ns


def units(X):
    """The members' units re-managed under X (difference method), plus counters."""
    U0 = M.units()
    P = prices()
    ev = {tf: SM.events(tf) for tf in ("1m", "5m", "15m", "1h")}
    out = {k: list(v) for k, v in U0.items()}
    n = collections.Counter()
    for src in ("EMA", "MD", "SR"):
        new = []
        for u in U0[src]:
            t = P.get((src, int(u["entry_t"]), int(u["dir"])))
            if t is None:
                n["no_price"] += 1
                new.append(u); continue
            rows, secs = rows_for(u)
            if not rows:
                n["no_bars"] += 1
                new.append(u); continue
            d = int(u["dir"])
            entry, stop, target = float(t["entry"]), float(t["stop"]), float(t["target"])
            spec = SPECS[src]
            base = _walk_secs(rows, secs, d, entry, stop, target, spec)
            n["base_same"] += int(abs(base["pts"] - u["pts"]) <= 0.5)
            n["all"] += 1
            if X.get("pstop"):
                o = X["pstop"]
                ns = pstop_at(u, o.get("tf", "5m"), d, entry, stop, float(o.get("cap", 2.0)))
                if ns is None:
                    new.append(u); continue
                risk1 = (entry - ns) * d
                tg = entry + d * 2.0 * risk1 if src == "SR" else target
                alt = _walk_secs(rows, secs, d, entry, ns, tg, spec)
                n["fired"] += 1
                pts = u["pts"] + (alt["pts"] - base["pts"])
                new.append({**u, "risk": round(risk1, 2), "tgt": round((tg - entry) * d, 2), "pts": round(pts, 4),
                            "w1": round(min(0.0, u["w1"] - (risk1 - (entry - stop) * d)), 4) if alt["kind"] == "STOP" else u["w1"],
                            "exit": alt["kind"], "exit_t": alt["t_exit"] or u["exit_t"]})
                continue
            rule = None
            if X.get("choch"):
                rule = {"kind": "choch", **X["choch"]}
            elif X.get("trail"):
                rule = {"kind": "trail", **X["trail"]}
            alt = _walk_secs(rows, secs, d, entry, stop, target, spec, rule, ev)
            if not alt["fired"]:
                new.append(u); continue
            n["fired"] += 1
            pts = u["pts"] + (alt["pts"] - base["pts"])
            new.append({**u, "pts": round(pts, 4), "w1": round(max(u["w1"], min(0.0, pts)), 4) if alt["t_exit"] and alt["t_exit"] < u["exit_t"] else u["w1"],
                        "exit": alt["kind"], "exit_t": min(int(u["exit_t"]), int(alt["t_exit"] or u["exit_t"]))})
        out[src] = new
    return out, dict(n)


def score_X(X):
    U = units(X)[0] if X else M.units()
    saved = M._UC["u"]
    M._UC["u"] = U
    try:
        A.no_hedge_real.__defaults__      # touch (same module)
        o = A.score(A.BASE)
    finally:
        M._UC["u"] = saved
    return o


def variants():
    V = collections.OrderedDict()
    V["base"] = {}
    for tf in ("5m", "15m"):
        for k in (0.5, 1.0):
            for act in ("exit", "be"):
                if act == "be" and k >= 1.0:
                    continue
                V[f"choch_{tf}_k{k}_{act}"] = {"choch": {"tf": tf, "k": k, "act": act}}
        for k in (0.5, 1.0):
            V[f"trail_{tf}_k{k}"] = {"trail": {"tf": tf, "k": k, "kinds": "any"}}
        for cap in (1.5, 2.0, 2.5, 3.0, 4.0):
            V[f"pstop_{tf}_cap{cap}"] = {"pstop": {"tf": tf, "cap": cap}}
    V["choch_1m_k1.0_exit"] = {"choch": {"tf": "1m", "k": 1.0, "act": "exit"}}
    for cap in (2.0, 2.5, 3.0):
        V[f"pstop_1h_cap{cap}"] = {"pstop": {"tf": "1h", "cap": cap}}
    return V


def fmt(o, s):
    x = o[s]
    return (f"{s} 2w {x['p10']}/{x['f10']} st {x['s10']} med {x['pass_med']} p60 {x['p60']} net {x['net']:+,} ({x['per_month']:+,}/mo) "
            f"PF {x['pf']} DD {x['dd']:,} tpw {x['tpw']} f3m ${x['fund_paid_3m']}")


def check():
    t0 = time.time()
    _, n = units({"choch": {"tf": "5m", "k": 99, "act": "exit"}})
    print("executor base vs the stored research points (within 0.5 pt):", n, f"({100.0 * n.get('base_same', 0) / max(1, n.get('all', 1)):.0f}%)")
    o = score_X({})
    for s in o:
        print("  ", fmt(o, s))
    print(f"{time.time() - t0:.0f} s")


RSPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
          "2021-24": ("2021-01-01", "2024-12-31")}


def rsum(U):
    """The members' own trades at a fixed risk: total R per span (no account rules, no sizing path)."""
    return {s: round(sum(u["pts"] / u["risk"] for src in ("EMA", "MD", "SR") for u in U[src] if a <= u["day"] <= z), 2)
            for s, (a, z) in RSPANS.items()}


def grid():
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for nm, X in variants().items():
        if nm in res and "r" in res[nm]:
            continue
        t1 = time.time()
        U, n = units(X) if X else (M.units(), {})
        o = score_X(X)
        res[nm] = {"X": X, "o": o, "n": n, "r": rsum(U)}
        print(f"{nm:24s} " + " | ".join(fmt(o, s) for s in o) + f" | fired {n.get('fired')} ({time.time() - t1:.0f}s)", flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


def gates(o, b, r=None, rb=None):
    """ATLAS gate: better 2-week pass - fail (incl. stuck) AND net in H1 and H2 on the 25K account, net not worse in 2025 and
    2021-24, the trade rate kept, AND the trades themselves better (total R at a fixed risk not lower in H1 and H2): an
    account gain that comes only from the sizing path is not an edge."""
    ok = all(o[s]["net"] > b[s]["net"] and (o[s]["p10"] - o[s]["dead10"]) >= (b[s]["p10"] - b[s]["dead10"]) for s in ("H1", "H2"))
    ref = all(o[s]["net"] >= b[s]["net"] for s in ("2025", "2021-24"))
    freq = o["H1"]["tpw"] >= b["H1"]["tpw"] - 0.05 and o["H2"]["tpw"] >= b["H2"]["tpw"] - 0.05
    trades = None if r is None or rb is None else all(r[s] >= rb[s] for s in ("H1", "H2"))
    return {"2026": ok, "2021-25": ref, "freq": freq, "trades_R": trades, "all": ok and ref and freq and trades is not False}


def report():
    res = json.load(open(OUT))
    b = res["base"]["o"]
    rb = res["base"].get("r")
    for nm, r in res.items():
        if nm == "base":
            continue
        o = r["o"]
        g = gates(o, b, r.get("r"), rb)
        d = {s: o[s]["net"] - b[s]["net"] for s in o}
        print(f"{'PASS' if g['all'] else '    '} {nm:24s} dnet " + " ".join(f"{s} {d[s]:+,}" for s in d)
              + f" | 2w H1 {o['H1']['p10']}/{o['H1']['dead10']} H2 {o['H2']['p10']}/{o['H2']['dead10']} | {g}")


SAVE = ["base", "choch_5m_k1.0_exit", "choch_5m_k0.5_be", "trail_15m_k1.0", "pstop_5m_cap2.5", "pstop_15m_cap2.0",
        "pstop_15m_cap3.0", "pstop_1h_cap3.0"]


def save():
    """rl.save runs atlas_struct_* (the back-to-back 25K eval path trades of every span, status from the gates)."""
    from tools import runlib as rl
    res = json.load(open(OUT))
    b = res["base"]["o"]
    for nm in SAVE:
        if nm not in res:
            continue
        X = res[nm]["X"]
        o = res[nm]["o"]
        g = gates(o, b, res[nm].get("r"), res["base"].get("r")) if nm != "base" else None
        M.units()
        saved = M._UC["u"]
        M._UC["u"] = units(X)[0] if X else saved
        try:
            _, paths = A.score(A.BASE, keep_paths=True)
        finally:
            M._UC["u"] = saved
        T = sorted((t for s in paths for t in paths[s]), key=lambda t: t["entry_t"])
        rows = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t.get("exit_t"), "dir": t["dir"], "pnl": t.get("pnl", 0.0),
                 "r": round(t["pnl"] / (t["risk"] * 2.0 * t["qty"]), 3) if t.get("qty") and t.get("risk") else None,
                 "risk_pts": t.get("risk"), "qty": t.get("qty"), "risk_usd": round(t["risk"] * 2.0 * t["qty"], 2) if t.get("qty") else None,
                 "exit": t.get("exit"), "trigger": t.get("src"), "low": t.get("low"), "half": False, "mfe": None, "mae": None,
                 "bars_held": None, "regime": "", "mult": 1.0} for t in T]
        st = "info" if nm == "base" else ("adopt-candidate" if g["all"] else "rejected")
        ver = " ; ".join(f"{s}: {fmt(o, s)}" + ("" if nm == "base" else f" (base {b[s]['net']:+,}, 2w {b[s]['p10']}/{b[s]['dead10']})")
                         for s in o) + (f" ; gates {g}" if g else "") + f" ; trades total R {res[nm].get('r')} (base {res['base'].get('r')})"
        rl.save(f"atlas_struct_{nm}", f"ATLAS structure management: {nm}", "management" if not nm.startswith("pstop") else "stops",
                "Owner 2026-10-28: trade like a person; ATLAS with structure exits / trails / the stop at the protected swing",
                params={"x_struct": X}, trades=rows, status=st, verdict=ver,
                notes="tools/structure_atlas.py: the members' stored research trades re-managed by the difference method (engine/advisor.walk, "
                      "96% of base trades within 0.5 pt of the stored points) on true 1m (2026) / 5m bars; scored by tools/atlas.score "
                      "(account-B rules, Builder 25K, need sizing). Trades = the back-to-back eval path of H1 / H2 / 2025 / 2021-24.",
                writeup="structure-management", tags=["atlas", "structure"])
        print("saved", nm, st)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"check": check, "grid": grid, "report": report, "save": save}[cmd]()
