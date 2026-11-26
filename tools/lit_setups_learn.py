"""LIT LEARNS FROM LIVE (day-litlearn 2026-11-26). RESEARCH ONLY: never writes live_model*.json, engine/, a live setting or an order.

Every LIT setup the engine sees (the 5m CISD candidates of engine/lit.candidates, 2021 -> the last bar on disk: the backtest AND the
live twin, since the PC bot runs the same code on the same bars) becomes one structured row:
  features at each step   sweep depth (ATR), inducements (live gate: within 1 ATR, <= 36 bars), displacement (ATR), the CISD bars,
                          VIX band (prior close), True Day Open side (00:00 ET open: discount / premium for the side), Silver Bullet
                          hour (03-04 / 10-11 / 14-15 ET), session; day_type / order_flow = None until big-regime / ticks land
  how far it got          the step it stopped at, in the Brain's words (engine/brain.STAGES): 0 outside hours, 2 sweep too shallow,
                          3 no inducement, 4 displacement too small, 6 limit not armed (stop size / no target), 7 never filled (limit
                          not tapped in time / no 1m CISD), 9 blocked by a day rule (1 a day, Monday rule, weekly stop, one at a time),
                          8 TAKEN
  outcome                taken: the live model's R and $; not taken: what it WOULD have done (the same engine with every gate open,
                          one trade at a time; "overlapped" when another open trade covered it)
Then:
  1. GATE LEDGER   each pre-registered gate opened alone (the real engine, real sizing, costs in) vs the live model, per span
                   (2026 Jan-Jun, Jul-Oct, 2021-25): the missed winners $ it cost vs the losers $ it avoided; + = the gate earns.
  2. SETUP REVIEW  the newest sessions' setups (twin, + the PC's live words / trades when data/pc_days is there): "setups like the
                   cancelled 09:31 short won X of Y" (same session, True Day Open side, depth and displacement bands, VIX band).
  3. SUGGESTIONS   pre-registered rule changes (VARIANTS below, written before any result was read) through the CLAUDE.md proof bar,
                   automatically: better than live on 2026 H1 (pick) AND Jul-Oct (net + PF), 2021-25 net not worse, walk-forward >=
                   5 of 7 blocks (2021..2025 yearly + 2026 H1 / H2), 2-4 trades a week in 2026, and NOT already in
                   docs/TESTED_AND_REJECTED.md. Pass = an "adopted-needs-owner-yes" journal card (nothing changes until the owner says
                   yes AND the full proof is re-run by hand); anything else = a "watching" line.
Outputs: research/learn/lit_setups.json (everything), journal lines in research/learn/journal.json (engine/market_learn.update_journal),
the Brain's LIT room (brain_state.json pillars.lit.setups).

    python -X utf8 tools/lit_setups_learn.py                  # everything (~1-2 min with the replay cache warm)
    python -X utf8 tools/lit_setups_learn.py --out logs/learning
    python -X utf8 tools/market_learn_weekly.py --nightly --litlearn     # as a nightly step
Tests: python -X utf8 -m tests.test_lit_setups_learn
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "research", "learn")
REJECTED = os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md")
PC_DAYS = os.path.join(ROOT, "data", "pc_days")
VERSION = 1
REVIEW_DAYS = 3                      # the newest sessions reviewed setup by setup
SIMILAR_MIN = 15                     # fewer like-for-like setups than this: one feature is dropped (the weakest first)

# ------------------------------------------------------------------------------------------------ pre-registered (2026-11-26, before any run)
# The steps (engine/brain.STAGES numbers) a setup can stop at, and the gate that stops it there.
STEP = {0: "outside hours", 2: "sweep too shallow", 3: "no inducement", 4: "displacement too small", 6: "limit not armed",
        7: "never filled", 8: "taken", 9: "blocked by a day rule"}
# Each gate opened ALONE (the ablation): name -> (step, plain words, the override of the live parameters)
GATES = {
    "window":     (0, "entry hours 02:00-15:30 ET", {"window": [[60, 945]]}),
    "depth":      (2, "sweep >= 0.5 ATR past the level", {"depth": 0.0}),
    "inducement": (3, "an inducement within 1 ATR, <= 36 bars", {"idm_a": None}),
    "disp":       (4, "displacement body >= 0.8 ATR", {"disp": 0.0}),
    "stop_size":  (6, "stop 8-80 points", {"min_stop": 0.0, "max_stop": 1e9}),
    "target":     (6, "a VIX-band target >= 1.5R away", {"fallback_rr": 4.0}),
    "limit_wait": (7, "the limit lives 6 bars (30 min)", {"wait": 12}),
    "cisd1m":     (7, "a 1m CISD within 22 bars after the tap", {"cisd1m": None}),
    "one_a_day":  (9, "one trade a day", {"max_per_day": 2}),
    "monday":     (9, "the Monday rule", {"monday": False}),
    "wk_stop":    (9, "the weekly stop (2 losses -> half size)", {"wk_stop": None}),
}
OPEN_ALL = {"window": [[60, 945]], "depth": 0.0, "idm_a": None, "disp": 0.0, "min_stop": 0.0, "max_stop": 1e9, "fallback_rr": 4.0,
            "max_per_day": 99, "monday": False, "wk_stop": None}
# The suggestion engine's rule changes: name -> (plain words, override | a skip filter name, words that find it in TESTED_AND_REJECTED)
VARIANTS = {
    "disp_0.6":     ("displacement >= 0.6 ATR (looser)", {"disp": 0.6}, [r"disp 0\.7/0\.6", r"disp 0\.6"]),
    "disp_1.0":     ("displacement >= 1.0 ATR (stricter)", {"disp": 1.0}, [r"disp 1\.0", r"disp 0\.7/0\.8/0\.9"]),
    "depth_0.3":    ("sweep >= 0.3 ATR (looser)", {"depth": 0.3}, [r"depth 0\.4/0\.3", r"depth 0\.3"]),
    "depth_0.75":   ("sweep >= 0.75 ATR (stricter)", {"depth": 0.75}, [r"depth 0\.75"]),
    "no_idm":       ("no inducement needed", {"idm_a": None}, [r"no inducement"]),
    "idm_2":        ("2 inducements needed", {"idm_a": [1.0, 36, 2]}, [r"2\+ inducement", r"idm 2"]),
    "wait_12":      ("the limit lives 12 bars (60 min)", {"wait": 12}, [r"limit (?:valid|lives) 12", r"wait 12"]),
    "cisd1m_15":    ("1m CISD within 15 bars", {"cisd1m": 15}, [r"cisd1m ?15", r"1m CISD within 15"]),
    "two_a_day":    ("a 2nd trade a day", {"max_per_day": 2}, [r"more trades", r"2nd trade"]),
    "no_monday":    ("no Monday rule", {"monday": False}, [r"Monday rule"]),
    "sb_only":      ("only Silver Bullet hours (03-04, 10-11, 14-15 ET)", "sb_only", [r"Silver Bullet"]),
    "tdo_side":     ("only on the True Day Open side (longs below, shorts above)", "tdo_side", [r"True Day Open side", r"TDO"]),
    "skip_vix25":   ("no trade when the prior VIX close >= 25", "skip_vix25", [r"VIX 25", r"high-VIX"]),
}
PROOF = {"walk_min": 5, "tpw": (2.0, 4.0)}


# ------------------------------------------------------------------------------------------------ small helpers
def _r(x, n=2):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, n) if v == v else None


def sess_of(mod: int) -> str:
    """ET minute of the entry bar -> session words"""
    return "London" if mod < 480 else "NY AM" if mod < 720 else "NY PM"


def sb_hour(mod: int) -> bool:
    """Silver Bullet hours (ICT): 03:00-04:00, 10:00-11:00, 14:00-15:00 ET"""
    return any(a <= mod < a + 60 for a in (180, 600, 840))


def vix_band(v) -> str | None:
    if v is None:
        return None
    return "VIX <15" if v < 15 else "VIX 15-20" if v < 20 else "VIX 20-25" if v < 25 else "VIX 25+"


def band(x, cuts, names):
    if x is None:
        return None
    for c, n in zip(cuts, names):
        if x < c:
            return n
    return names[-1]


def hm(mod: int) -> str:
    return f"{int(mod) // 60:02d}:{int(mod) % 60:02d}"


# ------------------------------------------------------------------------------------------------ the engine side (lit_final cache)
class Engine:
    """The live LIT parameters + the cached market / candidates (tools/lit_final.market) + run(P) = the real backtest."""

    def __init__(self):
        from tools import lit_final as F
        from tools import lit_robust as R
        self.F, self.P = F, R.live_params()
        self.M, self.C = F.market(self.P["ref"], self.P["extra_boxes"])
        # the backtest's session list (baseline run) + every weekday after it that has bars (the live twin's newest weeks)
        last = max(F.SESS)
        extra = sorted({z["day"] for z in self.C if z["day"] > last and dt.date.fromisoformat(z["day"]).weekday() < 5})
        self.sess = list(F.SESS) + extra
        self._vix = None

    def run(self, over=None, skip=None):
        P = {**self.P, **(over or {})}
        if skip:
            P["skip_keys"] = [list(k) for k in skip]
        return self.F.run(P, sessions=self.sess)

    def vix(self) -> dict:
        if self._vix is None:
            from engine import zeus_learn as Z
            self._vix = Z.vix_closes(ROOT)
        return self._vix


def _prior(d: dict, day: str):
    """the newest value dated before `day` (a sorted-keys walk; dicts of a few thousand days)"""
    ks = [k for k in d if k < day]
    return d[max(ks)] if ks else None


def features(E: Engine, z: dict, vix_days: list, vix: dict) -> dict:
    """The setup's facts at each step (only what was known at the CISD bar)."""
    import bisect
    M, P = E.M, E.P
    i = int(z["i"])
    dm, age, cnt = P["idm_a"] or (1.0, 36, 1)
    idm = sum(1 for dd, aa in z.get("idm_a") or [] if dd <= dm and aa <= age)
    k = bisect.bisect_left(vix_days, z["day"]) - 1
    v = vix[vix_days[k]] if k >= 0 else None
    tdo = float(M.open_00[i]) if M.open_00[i] == M.open_00[i] else None
    px = float(M.c[i])
    side = None if tdo is None else ("discount" if (px - tdo) * z["dir"] < 0 else "premium")
    return {"dir": int(z["dir"]), "mod": int(z["mod"]), "sess": sess_of(int(z["mod"])), "sb": sb_hour(int(z["mod"])),
            "depth": _r(z["depth_atr"], 3), "disp": _r(z["disp"], 3), "idm": idm, "cisd_bars": int(z.get("bars") or 0),
            "swept": list(z.get("swept") or [])[:4], "vix": _r(v, 2), "vix_band": vix_band(v), "tdo": side, "day_type": None, "of_state": None}


def first_gate(f: dict, P: dict) -> int | None:
    """The first setup gate of the live parameters this setup fails (engine/lit.setup_ok order), as a step number; None = passes."""
    if not any(a <= f["mod"] < b for a, b in P["window"]):
        return 0
    if (f["depth"] or 0) < P["depth"]:
        return 2
    if P.get("idm_a") and f["idm"] < P["idm_a"][2]:
        return 3
    if (f["disp"] or 0) < P["disp"]:
        return 4
    return None


def key(t) -> tuple:
    return (t["day"], int(t["i"]), int(t["dir"]))


def funnel(E: Engine, T_live=None, T_open=None) -> list:
    """One row a setup (2021 -> the last bar), with its step, outcome and features."""
    T_live = T_live if T_live is not None else E.run()
    T_open = T_open if T_open is not None else E.run(OPEN_ALL)
    live = {key(t): t for t in T_live}
    opn = {key(t): t for t in T_open}
    vix = E.vix()
    vd = sorted(vix)
    S = set(E.sess)
    rows = []
    for z in E.C:
        if z["day"] not in S:
            continue
        f = features(E, z, vd, vix)
        k = (z["day"], int(z["i"]), int(z["dir"]))
        t, o = live.get(k), opn.get(k)
        g = first_gate(f, E.P)
        if t is not None:
            step = 8
        elif g is not None:
            step = g
        elif o is not None:
            step = 6 if not (E.P["min_stop"] <= o["risk_pts"] <= E.P["max_stop"]) else 9
        else:
            step = 7
        src = t or o
        rows.append({"day": z["day"], "i": int(z["i"]), "t": int(z["entry_t"]), "step": step, "why": STEP[step], **f,
                     "r": _r(src["r"], 3) if src else None, "usd": _r(t["pnl"], 0) if t else None,
                     "would_usd": _r(o["pnl"], 0) if (o and not t) else None, "exit": (src or {}).get("exit"),
                     "outcome": "taken" if t else "would" if o else "overlapped" if step in (0, 2, 3, 4, 9) else "no fill"})
    return rows


# ------------------------------------------------------------------------------------------------ 1. the gate ledger
def _sp(F, T, nm):
    a, z = F.SPAN[nm]
    return [t for t in T if a <= t["day"] <= z]


def _pf(T):
    w = sum(t["pnl"] for t in T if t["pnl"] > 0)
    lo = -sum(t["pnl"] for t in T if t["pnl"] < 0)
    return round(w / lo, 2) if lo > 0 else None


def gate_ledger(E: Engine, T_live, runs: dict | None = None) -> list:
    """Each gate opened alone vs live: per span the trades it blocked (missed winners $, avoided losers $), the live trades the
    opened version lost by knock-on (one at a time / 1 a day), and the gate's value = live net - opened net (+ = it earns)."""
    F, out = E.F, []
    live_k = {key(t) for t in T_live}
    for name, (step, words, over) in GATES.items():
        T_g = runs[name] if runs and name in runs else E.run(over)
        row = {"gate": name, "step": step, "words": words, "spans": {}}
        for nm in ("H1", "H2", "2021-25"):
            L, G = _sp(F, T_live, nm), _sp(F, T_g, nm)
            gk = {key(t) for t in G}
            add = [t for t in G if key(t) not in live_k]
            lost = [t for t in L if key(t) not in gk]
            row["spans"][nm] = {"value": round(sum(t["pnl"] for t in L) - sum(t["pnl"] for t in G)),
                                "blocked_n": len(add), "missed_win_usd": round(sum(t["pnl"] for t in add if t["pnl"] > 0)),
                                "avoided_loss_usd": round(-sum(t["pnl"] for t in add if t["pnl"] < 0)),
                                "blocked_won": sum(1 for t in add if t["pnl"] > 0), "knock_on_usd": round(sum(t["pnl"] for t in lost)),
                                "pf_live": _pf(L), "pf_open": _pf(G)}
        v = [row["spans"][s]["value"] for s in ("H1", "H2", "2021-25")]
        row["verdict"] = "earns" if all(x > 0 for x in v) else "costs" if all(x < 0 for x in v) else "mixed"
        row["value_total"] = sum(v)
        out.append(row)
    return sorted(out, key=lambda r: r["value_total"])


# ------------------------------------------------------------------------------------------------ 2. "setups like this one"
LIKE = ("sess", "tdo", "depth_b", "disp_b", "vix_band", "dir")       # dropped from the right until >= SIMILAR_MIN alike


def _like(f):
    return {**f, "depth_b": band(f.get("depth"), (0.5, 1.5), ("<0.5", "0.5-1.5", "1.5+")),
            "disp_b": band(f.get("disp"), (0.8, 1.2), ("<0.8", "0.8-1.2", "1.2+"))}


def similar(rows: list, f: dict, before: str) -> dict:
    """setups alike (by LIKE fields) that happened before `before` and have an outcome (taken or would-have): won X of Y, avg R"""
    pool = [_like(r) for r in rows if r["day"] < before and r["r"] is not None]
    g = _like(f)
    for n in range(len(LIKE), 0, -1):
        ks = LIKE[:n]
        m = [r for r in pool if all(r.get(k) == g.get(k) for k in ks)]
        if len(m) >= SIMILAR_MIN or n == 1:
            won = sum(1 for r in m if r["r"] > 0)
            return {"n": len(m), "won": won, "avg_r": _r(sum(r["r"] for r in m) / len(m), 2) if m else None,
                    "on": [k for k in ks], "words": ", ".join(({1: "long", -1: "short"}.get(g.get(k)) if k == "dir" else str(g.get(k))) for k in ks if g.get(k) is not None)}
    return {"n": 0, "won": 0, "avg_r": None, "on": [], "words": ""}


def pc_live(days: list, root: str = ROOT) -> dict:
    """{day: {"words": [(t, kind, text)], "trades": [(entry_t, dir, usd)]}} from the PC's day folders when present (decisions =
    the Bot Brain's thought log, trades = the ledger, src live, bot LIT). Empty on a checkout without data/pc_days."""
    out = {}
    for d in days:
        base = os.path.join(PC_DAYS if root == ROOT else os.path.join(root, "data", "pc_days"), d)
        if not os.path.isdir(base):
            continue
        rec = {"words": [], "trades": []}
        for fn, kind in (("decisions.jsonl.gz", "words"), ("trades.jsonl.gz", "trades")):
            p = os.path.join(base, fn)
            if not os.path.exists(p):
                continue
            try:
                with gzip.open(p, "rt", encoding="utf-8") as fh:
                    for ln in fh:
                        try:
                            r = json.loads(ln)
                        except ValueError:
                            continue
                        if kind == "words" and r.get("kind") in ("armed", "expired", "rejected", "blocked", "entry", "tap", "cisd"):
                            rec["words"].append((int(r.get("t") or r.get("seen") or 0), r.get("kind"), str(r.get("text") or r.get("msg") or "")[:90]))
                        elif kind == "trades" and str(r.get("bot") or r.get("src") or "").lower() in ("lit", "zlarior", "live") \
                                and str(r.get("mode") or "live").lower() != "paper" and r.get("entry_t"):
                            rec["trades"].append((int(r["entry_t"]), int(r.get("dir") or (-1 if str(r.get("side")).upper() == "SHORT" else 1)),
                                                  _r(r.get("pnl") if r.get("pnl") is not None else r.get("usd"), 0)))
            except (OSError, EOFError):
                continue
        out[d] = rec
    return out


def review(rows: list, n_days: int = REVIEW_DAYS, live: dict | None = None) -> list:
    """the newest sessions' setups, each with its step and what alike setups did"""
    days = sorted({r["day"] for r in rows})[-n_days:]
    live = live if live is not None else pc_live(days)
    out = []
    for d in days:
        L = live.get(d) or {}
        for r in [x for x in rows if x["day"] == d]:
            s = similar(rows, r, d)
            item = {"day": d, "at": hm(r["mod"]), "side": "LONG" if r["dir"] == 1 else "SHORT", "step": r["step"], "why": r["why"],
                    "r": r["r"], "usd": r["usd"], "would_usd": r["would_usd"], "outcome": r["outcome"], "like": s,
                    "f": {k: r[k] for k in ("depth", "disp", "idm", "vix_band", "tdo", "sb", "sess")}}
            near = [w for w in L.get("words", []) if abs(w[0] - r["t"]) <= 15 * 60]
            if near:
                item["live_words"] = [f"{w[1]}: {w[2]}" for w in near[:3]]
            lt = [x for x in L.get("trades", []) if abs(x[0] - r["t"]) <= 15 * 60 and x[1] == r["dir"]]
            if lt:
                item["live_trade_usd"] = lt[0][2]
            item["words"] = sentence(item)
            out.append(item)
    return out


def sentence(it: dict) -> str:
    s = it["like"]
    head = f"{it['day'][5:]} {it['at']} {it['side'].lower()}"
    if it["step"] == 8:
        got = f"TAKEN, {('+' if (it['r'] or 0) >= 0 else '')}{it['r']}R" + (f" (${it['usd']:+,.0f})" if it.get("usd") is not None else "")
    else:
        got = f"stopped at step {it['step']} ({it['why']})"
        if it["r"] is not None:
            got += f"; would have made {('+' if it['r'] >= 0 else '')}{it['r']}R"
    like = (f"setups like it ({s['words']}) won {s['won']} of {s['n']}, avg {s['avg_r']:+.2f}R" if s["n"] and s["avg_r"] is not None
            else "no alike setups with an outcome yet")
    return f"{head}: {got}. {like}."


# ------------------------------------------------------------------------------------------------ 3. suggestions through the proof bar
def skip_for(name: str, rows: list) -> list:
    """the (day, i, dir) keys a filter variant skips"""
    if name == "sb_only":
        return [(r["day"], r["i"], r["dir"]) for r in rows if not r["sb"]]
    if name == "tdo_side":
        return [(r["day"], r["i"], r["dir"]) for r in rows if r["tdo"] == "premium"]
    if name == "skip_vix25":
        return [(r["day"], r["i"], r["dir"]) for r in rows if r["vix"] is not None and r["vix"] >= 25]
    raise KeyError(name)


def rejected_hits(pats: list, path: str = REJECTED) -> list:
    try:
        txt = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return []
    out = []
    for i, ln in enumerate(txt, 1):
        if any(re.search(p, ln, re.I) for p in pats):
            out.append(f"line {i}: {ln.strip()[:110]}")
    return out[:3]


def _net(T):
    return sum(t["pnl"] for t in T)


def walk_blocks(F):
    yrs = [(f"{y}", (f"{y}-01-01", f"{y}-12-31")) for y in range(2021, 2026)]
    return yrs + [("2026 H1", F.SPAN["H1"]), ("2026 H2", F.SPAN["H2"])]


def proof(E: Engine, T_live, T_v) -> dict:
    """The CLAUDE.md bar, automatically. Every number vs the live model."""
    F = E.F
    sc_l, sc_v = F.score(T_live, spans=("H1", "H2", "2026", "2021-25")), F.score(T_v, spans=("H1", "H2", "2026", "2021-25"))
    d = {nm: {"net": sc_v[nm]["net"] - sc_l[nm]["net"], "pf": sc_v[nm]["pf"], "pf_live": sc_l[nm]["pf"], "tpw": sc_v[nm]["tpw"]}
         for nm in ("H1", "H2", "2026", "2021-25")}
    wins, blocks = 0, []
    for nm, (a, z) in walk_blocks(F):
        dl = _net([t for t in T_live if a <= t["day"] <= z])
        dv = _net([t for t in T_v if a <= t["day"] <= z])
        blocks.append([nm, round(dv - dl)])
        wins += dv > dl
    pf = lambda nm: (d[nm]["pf"] or 0) >= (d[nm]["pf_live"] or 0)  # noqa: E731
    gates = {"pick_h1": d["H1"]["net"] > 0 and pf("H1"), "check_jul_oct": d["H2"]["net"] > 0 and pf("H2"),
             "y2021_25": d["2021-25"]["net"] >= 0, "walk_forward": wins >= PROOF["walk_min"],
             "trades_week": PROOF["tpw"][0] <= (sc_v["2026"]["tpw"] or 0) <= PROOF["tpw"][1]}
    return {"delta": d, "walk": blocks, "walk_wins": wins, "gates": gates, "pass": all(gates.values())}


def suggestions(E: Engine, T_live, rows: list) -> list:
    out = []
    for name, (words, over, pats) in VARIANTS.items():
        T_v = E.run(skip=skip_for(over, rows)) if isinstance(over, str) else E.run(over)
        pr = proof(E, T_live, T_v)
        hits = rejected_hits(pats)
        status = "adopted-needs-owner-yes" if pr["pass"] and not hits else "watching"
        out.append({"name": name, "words": words, "status": status, "already_tested": hits, **pr})
    return out


# ------------------------------------------------------------------------------------------------ the report
def build(say=print) -> dict:
    t0 = time.time()
    E = Engine()
    T_live = E.run()
    runs = {nm: E.run(g[2]) for nm, g in GATES.items()}
    T_open = E.run(OPEN_ALL)
    rows = funnel(E, T_live, T_open)
    say(f"lit_setups: {len(rows)} setups, {sum(r['step'] == 8 for r in rows)} taken ({time.time() - t0:.0f} s)")
    G = gate_ledger(E, T_live, runs)
    R = review(rows)
    S = suggestions(E, T_live, rows)
    by_step = collections.Counter(r["step"] for r in rows)
    steps = []
    for st in sorted(by_step):
        rr = [r for r in rows if r["step"] == st]
        wr = [r for r in rr if r["r"] is not None]
        steps.append({"step": st, "why": STEP[st], "n": len(rr), "with_outcome": len(wr), "won": sum(1 for r in wr if r["r"] > 0),
                      "avg_r": _r(sum(r["r"] for r in wr) / len(wr), 3) if wr else None})
    doc = {"v": VERSION, "kind": "lit-setups", "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "paper_only": True,
           "data_end": max(r["day"] for r in rows), "setups": len(rows), "taken": by_step.get(8, 0), "steps": steps, "gates": G,
           "review": R, "suggestions": S, "variants_tested": len(S),
           "note": "Research only. A suggestion goes live only after the owner says yes AND the full CLAUDE.md proof is re-run by hand."}
    say(f"lit_setups: built in {time.time() - t0:.0f} s, data to {doc['data_end']}")
    return doc


def journal_obs(doc: dict) -> list:
    """the journal lines: one per gate, one per suggestion, one per reviewed day"""
    obs = []
    mo = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    h2 = f"Jul-{mo[int(doc['data_end'][5:7]) - 1]} {int(doc['data_end'][8:10])}"      # the 2nd half runs to the newest bar (the live twin's weeks)
    for g in doc["gates"]:
        s = g["spans"]
        v = [s[k]["value"] for k in ("H1", "H2", "2021-25")]
        word = "earns" if g["verdict"] == "earns" else "COSTS" if g["verdict"] == "costs" else "is mixed"
        obs.append({"pillar": "lit", "lens": "setup gate", "key": f"litlearn|gate|{g['gate']}",
                    "status": "confirmed" if g["verdict"] != "mixed" else "watching",
                    "noticed": (f"Gate step {g['step']} '{g['words']}' {word}: {'+' if v[0] >= 0 else ''}${v[0]:,} / "
                                f"{'+' if v[1] >= 0 else ''}${v[1]:,} / {'+' if v[2] >= 0 else ''}${v[2]:,} (Jan-Jun / Jul-Oct / 2021-25); "
                                f"it blocked {sum(s[k]['blocked_n'] for k in s)} trades: missed winners "
                                f"${sum(s[k]['missed_win_usd'] for k in s):,}, avoided losers ${sum(s[k]['avoided_loss_usd'] for k in s):,}"),
                    "evidence": {"usd": g["value_total"], "h1": v[0], "h2": v[1], "y21_25": v[2]}})
    for s in doc["suggestions"]:
        g = s["gates"]
        failed = [k for k, ok in g.items() if not ok]
        why = ("passed every gate: needs the owner's yes" if s["status"] != "watching"
               else ("already tested and rejected (" + s["already_tested"][0][:60] + ")" if s["already_tested"] and not failed
                     else "failed: " + ", ".join(failed)))
        obs.append({"pillar": "lit", "lens": "setup suggestion", "key": f"litlearn|prop|{s['name']}", "status": s["status"],
                    "noticed": (f"Suggestion '{s['words']}': Jan-Jun {s['delta']['H1']['net']:+,} $, Jul-Oct {s['delta']['H2']['net']:+,} $, "
                                f"2021-25 {s['delta']['2021-25']['net']:+,} $, walk-forward {s['walk_wins']}/7 vs live; {why}"),
                    "evidence": {"usd": s["delta"]["H2"]["net"], "h1": s["delta"]["H1"]["net"], "y21_25": s["delta"]["2021-25"]["net"],
                                 "walk": s["walk_wins"], "tested": doc["variants_tested"]}})
    for d in sorted({r["day"] for r in doc["review"]}):
        its = [r for r in doc["review"] if r["day"] == d]
        cancel = [r for r in its if r["step"] != 8 and r["step"] != 0]
        top = max(cancel, key=lambda r: r["like"]["n"] * (abs(r["like"]["avg_r"] or 0)), default=None)
        taken = [r for r in its if r["step"] == 8]
        txt = (f"{d}: {len(its)} LIT setups, {len(taken)} taken"
               + (f" ({', '.join(f'{r['at']} {r['side'].lower()} {r['r']:+}R' for r in taken if r['r'] is not None)})" if taken else "")
               + (f". {top['words']}" if top else ""))
        obs.append({"pillar": "lit", "lens": "setup review", "key": f"litlearn|day|{d}", "status": "watching", "date": d, "noticed": txt[:400],
                    "evidence": {"n": len(its), "taken": len(taken)}})
    return obs


def brain_room(doc: dict) -> dict:
    """the LIT room's block (brain_state.json pillars.lit.setups): small, plain words"""
    G = doc["gates"]
    cost = [g for g in G if g["value_total"] < 0][:2]
    earn = sorted([g for g in G if g["value_total"] > 0], key=lambda g: -g["value_total"])[:2]
    last = doc["review"][-6:]
    return {"data_end": doc["data_end"], "setups": doc["setups"], "taken": doc["taken"],
            "funnel": [[s["step"], s["why"], s["n"]] for s in doc["steps"]],
            "costs_most": [f"{g['words']} ({g['value_total']:+,} $ over 2021-26)" for g in cost],
            "earns_most": [f"{g['words']} ({g['value_total']:+,} $ over 2021-26)" for g in earn],
            "recent": [r["words"] for r in last],
            "needs_owner_yes": sum(1 for s in doc["suggestions"] if s["status"] == "adopted-needs-owner-yes"),
            "watching": sum(1 for s in doc["suggestions"] if s["status"] == "watching")}


def write(doc: dict, out_dir: str = OUT_DIR, today: str | None = None) -> dict:
    """lit_setups.json + journal lines + the Brain's LIT room. Only files under out_dir."""
    from engine import market_learn as M
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "lit_setups.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    jp = os.path.join(out_dir, "journal.json")
    J, added = M.update_journal(M.journal_doc(jp), journal_obs(doc), today=today)
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(J, fh, indent=1, default=str)
    bp = os.path.join(out_dir, "brain_state.json")
    try:
        S = json.load(open(bp, encoding="utf-8"))
    except (OSError, ValueError):
        S = {"v": 1, "kind": "brain-state", "paper_only": True, "pillars": {}}
    lit = S.setdefault("pillars", {}).setdefault("lit", {"name": "LIT (Zlarior)"})
    lit["setups"] = brain_room(doc)
    lit["needs_owner_yes"] = max(int(lit.get("needs_owner_yes") or 0), lit["setups"]["needs_owner_yes"])
    with open(bp, "w", encoding="utf-8") as fh:
        json.dump(S, fh, indent=1, default=str)
    return {"added": added, "journal": len(J)}


def step(out_dir: str | None = None, say=print) -> dict:
    """the nightly step (tools/market_learn_weekly.py --nightly --litlearn): build + write; never raises into the caller"""
    try:
        doc = build(say=say)
        w = write(doc, out_dir or OUT_DIR)
        say(f"lit_setups: {len(w['added'])} journal lines new or changed; owner cards {brain_room(doc)['needs_owner_yes']}")
        return {"ok": True, "doc": doc, **w}
    except Exception as ex:  # noqa: BLE001
        say(f"lit_setups skipped ({ex.__class__.__name__}: {str(ex)[:160]})")
        return {"ok": False, "err": str(ex)[:160]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="folder for lit_setups.json + journal.json + brain_state.json (default research/learn)")
    a = ap.parse_args(argv)
    from engine import market_learn as M
    before = M.hashes(ROOT)
    r = step(a.out)
    if M.hashes(ROOT) != before:
        raise SystemExit("A LIVE FILE CHANGED during lit_setups_learn")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
