"""PROMETHEUS fitness (2026 H1 only) and checks (2026 H2, 2021-25), on the repo's own LIT backtest path.

Nothing here re-implements LIT:
  trades     tools/lit_final.run(P, sessions) = engine/lit.py run_x on the cached LIT candidates (the code the live loop runs;
             with the live params it reproduces run lit_live: H1 80 trades +$33,901)
  eval path  tools/lit_adopt_combo.units (engine trades -> per-micro units) + tools/lit_adv_manage.run_eval (one MFFU Builder
             50K eval sized by engine/sizing.lit_qty: two_week for 10 sessions, then safe_eval, $1.90 a micro), started on
             every session of the span, counted like lit_adv_manage.evals (only starts that can see 10 sessions)

Fitness (the owner's two goals, each scaled so the live strategy scores 1.0 on it):
  fit = 0.5 x ($ per month / live $ per month) + 0.5 x ((p10 - f10) / live (p10 - f10)) - 0.5 x (trades/week short of 2)
        - 0.25 x (trades/week over 4)
  $ per month: the LIT size rule ($800 up to a 20-pt stop, the weekly stop), costs in = how run lit_live is scored
  p10 / f10:   % of evals passed / failed within 10 sessions on the eval path (the live two_week sizing)
The fitness sees 2026-01-02 .. 2026-06-30 only: the sessions handed to run_x are H1 sessions, every trade and every eval unit
is asserted to be in H1 (`assert_h1`), and the eval starts / sessions are H1 indices of lit_adv_manage.S26.
"""
from __future__ import annotations

import collections
import functools
import hashlib
import json
import os

import numpy as np

from tools.prometheus import genome as G

ROOT = G.ROOT
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
H1_END = SPANS["H1"][1]
W_MONEY, W_SPEED, PEN_LOW, PEN_HIGH = 0.5, 0.5, 0.5, 0.25
CACHE_DIR = os.path.join(ROOT, "research", "runs", "_cache")     # gitignored (runlib's replay cache)
FIT_V = "v1"                                                      # bump when the fitness or its inputs change


# ------------------------------------------------------------------------------------------------ repo backtest path (lazy)
@functools.lru_cache(maxsize=None)
def _mods():
    from tools import lit_final as F
    from tools import lit_adv_manage as A
    from tools import lit_adopt_combo as AC
    return F, A, AC


def sessions(span: str) -> list:
    F, _, _ = _mods()
    a, z = SPANS[span]
    return [d for d in F.SESS if a <= d <= z]


def assert_h1(rows, what="trades"):
    """Every row's day is a 2026 H1 session: the fitness never sees H2 (or 2021-25)."""
    bad = [r["day"] for r in rows if not (SPANS["H1"][0] <= r["day"] <= H1_END)]
    assert not bad, f"fitness saw {len(bad)} {what} outside 2026 H1, e.g. {bad[:3]}"


def run_trades(g, sess) -> list:
    """LIT trades of genome g on these sessions (LIT size rule, costs in)."""
    F, _, _ = _mods()
    return F.run(G.lit_params(g), sess)


def eval_cfg(g) -> dict:
    """The eval sizing config of genome g, built exactly as tools/lit_adv_manage.CFG builds the live one."""
    ls = G.to_model(g)["lit_sizing"]
    return {**{k: ls[k] for k in ("two_week", "safe_cap", "eval_ref_stop", "fast_ref_stop")}, "mode": "two_week",
            "two_week_until": ls.get("two_week_until", 10), "after_mode": ls.get("after_mode", "safe_eval")}


def eval_path(U, span, cfg) -> dict:
    """p10 / f10 / p20 / f20 / pass_med of fresh 50K evals started on every session of span (2026 H1 or H2), as
    lit_adv_manage.evals but with this genome's sizing config."""
    _, A, _ = _mods()
    by = A.by_day(U)
    a, z = A.span_ix(span)
    res = [(A.run_eval(list(range(i, min(z, i + 20))), by, cfg=cfg), z - i) for i in range(a, z)]
    o = {}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    return o


def lit_stats(T, sess) -> dict:
    """Headline numbers of the LIT size rule on these sessions: trades, trades/week, % weeks with 2+, win %, PF, net,
    $ per month (21 sessions), max drawdown."""
    from engine import lit
    n_s = len(sess)
    if not T:
        return {"n": 0, "tpw": 0.0, "wk2": 0, "win": None, "pf": None, "net": 0, "pm": 0, "dd": 0}
    T = sorted(T, key=lambda t: t["entry_t"])
    p = np.array([float(t["pnl"]) for t in T])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    wk = collections.Counter(lit.iso_week(t["day"]) for t in T)
    allwk = {lit.iso_week(d) for d in sess}
    return {"n": len(T), "tpw": round(len(T) / (n_s / 5), 2), "wk2": round(100 * sum(wk[w] >= 2 for w in allwk) / len(allwk)),
            "win": round(100 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "pm": round(float(p.sum()) / (n_s / 21)), "dd": round(dd)}


# ------------------------------------------------------------------------------------------------ fitness (H1 only)
def h1_metrics(g) -> dict:
    """Everything the fitness needs, from 2026 H1 only."""
    _, _, AC = _mods()
    sess = sessions("H1")
    assert sess and sess[-1] <= H1_END
    T = run_trades(g, sess)
    assert_h1(T)
    U = AC.units(T)
    assert_h1(U, "eval units")
    m = lit_stats(T, sess)
    e = eval_path(U, "H1", eval_cfg(g))
    return {**m, "p10": e["p10"], "f10": e["f10"], "p20": e["p20"], "f20": e["f20"], "pass_med": e["pass_med"],
            "last_day": max((t["day"] for t in T), default=None)}


def score(m, ref) -> float:
    """The fitness of H1 metrics m, scaled by the live strategy's H1 metrics ref (live = 1.0 when it trades 2-4 a week)."""
    money = m["pm"] / ref["pm"] if ref["pm"] else 0.0
    sp_ref = ref["p10"] - ref["f10"]
    speed = (m["p10"] - m["f10"]) / sp_ref if sp_ref else 0.0
    pen = PEN_LOW * max(0.0, 2.0 - m["tpw"]) + PEN_HIGH * max(0.0, m["tpw"] - 4.0)
    return round(W_MONEY * money + W_SPEED * speed - pen, 5)


class Fitness:
    """Cached H1 fitness: f(genome) -> (fit, metrics). The cache is keyed by the genome, the data and the model file, and kept
    on disk in research/runs/_cache (gitignored) so a rerun or another seed costs nothing."""

    def __init__(self, persist: bool = True):
        self.persist = persist
        self.calls = 0
        self.path = os.path.join(CACHE_DIR, f"prometheus_fit_{FIT_V}_{self._stamp()}.json")
        self.cache = {}
        if persist and os.path.exists(self.path):
            try:
                self.cache = json.load(open(self.path, encoding="utf-8"))
            except ValueError:
                self.cache = {}
        self.ref = self.metrics(G.live_genome())

    @staticmethod
    def _stamp():
        from tools import runlib as rl
        m = G.load_model()
        h = hashlib.sha1(json.dumps({"lit": m["lit"], "lit_sizing": m["lit_sizing"], "knobs": G.spec()}, sort_keys=True).encode())
        return rl._data_key().replace(":", "_") + "_" + h.hexdigest()[:8]

    def metrics(self, g) -> dict:
        k = G.key(g)
        if k not in self.cache:
            self.calls += 1
            self.cache[k] = h1_metrics(g)
        return self.cache[k]

    def __call__(self, g):
        m = self.metrics(g)
        return score(m, self.ref), m

    def save(self):
        if self.persist:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = f"{self.path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.cache, fh, separators=(",", ":"))
            os.replace(tmp, self.path)


# ------------------------------------------------------------------------------------------------ checks (after the GA)
def check(g, full: bool = False) -> dict:
    """H1 / H2 / 2021-25 numbers of genome g from one run over every session (the way run lit_live is scored). H1 / H2:
    LIT size rule + the eval path (two_week); 2021-25: the LIT size rule (no 1m bars and no eval-path units there);
    full=True adds the LIT-size-rule eval speed (rl.eval_speed: p10 / f10 on every span) and the daily P&L."""
    F, _, AC = _mods()
    T = run_trades(g, F.SESS)
    cfg = eval_cfg(g)
    U = AC.units(T)
    out = {}
    for span in ("H1", "H2", "2021-25"):
        sess = sessions(span)
        a, z = SPANS[span]
        TT = [t for t in T if a <= t["day"] <= z]
        o = lit_stats(TT, sess)
        if span != "2021-25":
            e = eval_path(U, span, cfg)
            o.update(p10=e["p10"], f10=e["f10"], p20=e["p20"], f20=e["f20"], pass_med=e["pass_med"])
        if full:
            from tools import runlib as rl
            days = rl.days_of(TT, sess)
            sp = rl.eval_speed(days, horizon=20, full_only=True)
            o["lit_p10"], o["lit_f10"] = sp["p10"], sp["f10"]
            pn = sorted((t["pnl"] for t in TT), reverse=True)
            o["net_x3"] = round(sum(pn[3:]))
            o["_days"] = [[d["date"], d["pnl"]] for d in days]
        out[span] = o
    if full:
        out["_trades"] = T
    return out
