"""Robustness card for the live LIT (competitor-features #12, 2026-10-21): how much of the live config's 2026 money survives
when the world is a little worse than the backtest.

Tests (live_model.json "lit", LIT size rule = run lit_live; 2026 only, pick H1 / check H2 as every LIT result):
  noise1 / noise2   every 5m and 1m bar's open / high / low / close moved by a random -1..+1 / -2..+2 ticks (high / low
                    widened to keep the bar valid), the market + setups rebuilt on the noisy bars (50 seeded copies each)
  slip03            random slippage 0-3 ticks on every entry and every exit, targets included (500 seeded draws)
  miss10 / miss20   a random 10% / 20% of the trades never fill (500 seeded draws)
  delay1 / delay2   the 1m-CISD entry fills 1 / 2 bars later (engine option entry_delay, research only)
  worst             noise1 + slip 0-2 ticks + miss 10% + delay 1 together (50 seeded copies)
Per test: % of the 2026 / H1 / H2 $ kept (mean, p10, p90), PF range, MFFU 2-week pass / fail range (fresh eval on every
session, as every LIT run is scored), trades a week. Each test's median copy is stored as a run (tools/runlib.py rl.save,
runs lit_robust_<test>) and the whole card goes to research/lab/robust.json (the Performance -> Robustness page).

  python -X utf8 tools/lit_robust.py            # ~10 min on one core (2026 window from 2025-10-01: 4 s a replay)
  python -X utf8 tools/lit_robust.py --quick    # 6 noisy copies, 60 draws (a check, nothing stored as a run)
Read-only research: changes nothing in live_model.json and no engine default. Reuses the robustness idea and the
entry_delay / slippage handling of tools/lit_batch3b.py (robust_one), on the plain live config instead of the combo.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.data import Bars, load  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "robust.json")
WIN_START = "2025-10-01"           # enough history for PMH / PWH, build-ups and a warm ATR (the 2026 trades equal run lit_live)
SPANS = ("H1", "H2", "2026")
TICK = 0.25
VERSION = 1


def live_params():
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    return {**lit.DEFAULTS, **lm["lit"]}


class Win:
    """The 2026 window: clean 5m bars, the clean market, its 1m executor bars and the 2026 sessions."""

    def __init__(self, P):
        from tools import lit_final as F
        self.F, self.P = F, P
        b = load("NQ", "5m")
        a = int(np.searchsorted(np.array(b.date_str), WIN_START))
        self.B = b.slice(a, len(b))
        self.M = lit.Market(extra_boxes=P["extra_boxes"], bars=self.B)
        self.C = lit.candidates(self.M, ref=P["ref"])
        self.B1 = lit.bars_1m(self.M) if P["tf"] == "1m" else None
        self.S = [d for d in F.SESS if d >= "2026-01-01"]

    def run(self, P=None, noise=0, seed=0):
        P = {**self.P, **(P or {})}
        if not noise:
            return lit.run_x(self.M, self.C, P, self.S, B1=self.B1, B5=lit.bars_5m(self.M))
        rng = np.random.default_rng(seed)
        o, h, l, c = _noisy(rng, noise, self.B.o, self.B.h, self.B.l, self.B.c)
        B = self.B
        Bn = Bars(B.sym, B.tf, B.t, o, h, l, c, B.v, B.mod, B.tday, B.dow, B.date_str)
        M = lit.Market(extra_boxes=P["extra_boxes"], bars=Bn)
        C = lit.candidates(M, ref=P["ref"])
        B1 = None
        if self.B1 is not None:
            X = self.B1
            o1, h1, l1, c1 = _noisy(rng, noise, X.o, X.h, X.l, X.c)
            B1 = lit.XBars(X.t, o1, h1, l1, c1, X.mod, X.day, X.secs, X.full)
        return lit.run_x(M, C, P, self.S, B1=B1, B5=lit.bars_5m(M))


def _noisy(rng, k, o, h, l, c):
    """Each price moved by a random whole number of ticks in [-k, k]; high / low widened to keep o, c inside."""
    n = len(o)
    d = rng.integers(-k, k + 1, size=(4, n)) * TICK
    o2, h2, l2, c2 = o + d[0], h + d[1], l + d[2], c + d[3]
    h2 = np.maximum.reduce([h2, o2, c2])
    l2 = np.minimum.reduce([l2, o2, c2])
    return o2, h2, l2, c2


def slip_trades(T, rng, lo=0, hi=3):
    """Random slippage per fill (entry and exit, targets too): lo..hi ticks each, on every micro (scale-in adds too)."""
    out = []
    for t in T:
        ticks = int(rng.integers(lo, hi + 1)) + int(rng.integers(lo, hi + 1))
        q = int(t.get("qty_total") or t["qty"])
        usd = ticks * TICK * lit.PV * q
        out.append({**t, "pnl": round(t["pnl"] - usd, 2), "low": round(float(t.get("low") or 0.0) - usd, 2)})
    return out


def drop_trades(T, rng, frac):
    keep = rng.random(len(T)) >= frac
    return [t for t, k in zip(T, keep) if k]


def score(F, T):
    o = F.score(T, spans=SPANS)
    return {s: {k: o[s].get(k) for k in ("n", "tpw", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_rate")}
            for s in SPANS}


def _q(xs, p):
    xs = [x for x in xs if x is not None]
    return None if not xs else round(float(np.percentile(xs, p)), 2)


def agg(base, reps):
    """reps: list of score() dicts -> mean / p10 / p90 of net, kept %, PF, 2-week pass / fail per span."""
    out = {}
    for s in SPANS:
        b = base[s]["net"] or 1
        nets = [r[s]["net"] for r in reps]
        out[s] = {"net": round(float(np.mean(nets))), "net_p10": round(_q(nets, 10)), "net_p90": round(_q(nets, 90)),
                  "keep": round(100.0 * float(np.mean(nets)) / b, 1), "keep_p10": round(100.0 * _q(nets, 10) / b, 1),
                  "keep_p90": round(100.0 * _q(nets, 90) / b, 1),
                  "pf": _q([r[s]["pf"] for r in reps], 50), "pf_p10": _q([r[s]["pf"] for r in reps], 10),
                  "pf_p90": _q([r[s]["pf"] for r in reps], 90),
                  "p10": _q([r[s]["p10"] for r in reps], 50), "p10_lo": _q([r[s]["p10"] for r in reps], 10),
                  "p10_hi": _q([r[s]["p10"] for r in reps], 90),
                  "f10": _q([r[s]["f10"] for r in reps], 50), "f10_lo": _q([r[s]["f10"] for r in reps], 10),
                  "f10_hi": _q([r[s]["f10"] for r in reps], 90),
                  "tpw": _q([r[s]["tpw"] for r in reps], 50), "dd": _q([r[s]["dd"] for r in reps], 50),
                  "profitable": round(100.0 * sum(1 for x in nets if x > 0) / len(nets), 1),
                  "pf_over2": round(100.0 * sum(1 for r in reps if (r[s]["pf"] or 0) > 2) / len(reps), 1)}
    return out


TESTS = [
    ("noise1", "Prices +/-1 tick (every 5m / 1m OHLC)", "noise", {"noise": 1}),
    ("noise2", "Prices +/-2 ticks (every 5m / 1m OHLC)", "noise", {"noise": 2}),
    ("slip03", "Random slippage 0-3 ticks on every fill", "post", {"slip": (0, 3)}),
    ("miss10", "10% of trades missed at random", "post", {"miss": 0.10}),
    ("miss20", "20% of trades missed at random", "post", {"miss": 0.20}),
    ("delay1", "Entry 1 minute late", "opt", {"entry_delay": 1}),
    ("delay2", "Entry 2 minutes late", "opt", {"entry_delay": 2}),
    ("worst", "All at once: +/-1 tick, slip 0-2, 10% missed, 1 min late", "noise", {"noise": 1, "slip": (0, 2), "miss": 0.10,
                                                                                    "entry_delay": 1}),
]


def main(argv):
    quick = "--quick" in argv
    n_noise, n_post = (6, 60) if quick else (50, 500)
    t0 = time.time()
    P = live_params()
    W = Win(P)
    F = W.F
    T0 = W.run()
    base = score(F, T0)
    run = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    k_run = sorted((r[0], int(r[1])) for r in run["trades"] if r[0] >= "2026-01-01")
    same = sorted((t["day"], int(t["entry_t"])) for t in T0) == k_run
    print(f"base: {len(T0)} trades, 2026 net {base['2026']['net']:+,} PF {base['2026']['pf']} (== run lit_live: {same})", flush=True)
    res = {}
    for tid, label, kind, cfg in TESTS:
        t1 = time.time()
        reps, copies = [], []
        opts = {"entry_delay": cfg["entry_delay"]} if cfg.get("entry_delay") else {}
        if kind == "opt":
            T = W.run(opts)
            reps, copies = [score(F, T)], [T]
        else:
            n = n_noise if kind == "noise" else n_post
            Tc = None if kind == "noise" else T0
            for i in range(n):
                rng = np.random.default_rng(20261021 + 1000 * len(res) + i)
                T = W.run(opts, noise=cfg["noise"], seed=int(rng.integers(1 << 30))) if kind == "noise" else list(Tc)
                if cfg.get("slip"):
                    T = slip_trades(T, rng, *cfg["slip"])
                if cfg.get("miss"):
                    T = drop_trades(T, rng, cfg["miss"])
                reps.append(score(F, T))
                copies.append(T)
        A = agg(base, reps)
        mid = int(np.argsort([r["2026"]["net"] for r in reps])[len(reps) // 2])
        Tm = copies[mid] if copies[mid] is not None else None
        changed = None
        if Tm is not None:
            kb = {(t["day"], int(t["entry_t"])) for t in T0}
            km = {(t["day"], int(t["entry_t"])) for t in Tm}
            changed = {"same": len(kb & km), "lost": len(kb - km), "new": len(km - kb)}
        res[tid] = {"label": label, "kind": kind, "cfg": {k: list(v) if isinstance(v, tuple) else v for k, v in cfg.items()},
                    "reps": len(reps), **A, "changed": changed, "_mid": mid, "_T": Tm}
        a = A["2026"]
        print(f"  {tid:7s} {label:58s} keep {a['keep']:5.1f}% ({a['keep_p10']}..{a['keep_p90']}) PF {a['pf']} ({a['pf_p10']}..{a['pf_p90']}) "
              f"2w {a['p10']}/{a['f10']} H1 {A['H1']['keep']}% H2 {A['H2']['keep']}%  {time.time() - t1:.0f}s", flush=True)
    card = card_lines(base, res)
    out = {"v": VERSION, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
           "run": "lit_live", "same_as_run": same, "window": WIN_START, "quick": quick, "base": base,
           "tests": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in res.items()}, "card": card,
           "method": ("Live LIT (live_model.json lit, LIT size rule = run lit_live), 2026 sessions, replayed on a window from "
                      f"{WIN_START}. Noise: every 5m and 1m open / high / low / close moved by a random whole number of ticks, the "
                      "market and the setups rebuilt on the noisy bars. Slippage / missed: re-scored after the fact on the "
                      "replay's trades (exact: P&L is linear in the ticks). Delay: engine option entry_delay (research only). "
                      "Eval odds = a fresh MFFU 50K started on every session (2-week pass / fail).")}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if not quick:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        store(base, res)
    print(json.dumps(card, indent=1))
    print(f"-> {OUT if not quick else '(quick: not written)'} in {time.time() - t0:.0f}s")
    return 0


def card_lines(base, res):
    """The plain-language card: one line per test + the headline."""
    g = lambda k, s="2026": res[k][s]
    lines = []
    for tid, v in res.items():
        a, h1, h2 = v["2026"], v["H1"], v["H2"]
        rng_ = f" ({a['keep_p10']:.0f}-{a['keep_p90']:.0f}%)" if v["reps"] > 1 else ""
        lines.append({"id": tid, "label": v["label"],
                      "text": f"{v['label']}: keeps {a['keep']:.0f}% of the 2026 $" + rng_ + f", PF {a['pf']}"
                              + (f" ({a['pf_p10']}-{a['pf_p90']})" if v["reps"] > 1 else "")
                              + f", 2-week pass/fail {a['p10']}/{a['f10']}%; H1 {h1['keep']:.0f}%, H2 {h2['keep']:.0f}%",
                      "keep": a["keep"], "keep_h1": h1["keep"], "keep_h2": h2["keep"], "pf": a["pf"],
                      "ok": a["keep"] >= 70 and (a["pf"] or 0) >= 2})
    weak = min(res, key=lambda k: g(k)["keep"])
    head = (f"Live LIT on 2026 keeps {g('noise1')['keep']:.0f}% of its $ with prices +/-1 tick ({g('noise1')['profitable']:.0f}% of "
            f"{res['noise1']['reps']} noisy copies profitable), {g('slip03')['keep']:.0f}% with 0-3 ticks of random slippage and "
            f"{g('miss20')['keep']:.0f}% with 20% of trades missed. Weakest: {res[weak]['label'].lower()} ({g(weak)['keep']:.0f}%).")
    return {"headline": head, "lines": lines, "weakest": weak,
            "base": {s: {k: base[s][k] for k in ("n", "net", "pf", "p10", "f10")} for s in SPANS}}


def store(base, res):
    from tools import runlib as rl
    from tools import lit_final as F
    P = live_params()
    for tid, v in res.items():
        T = v.get("_T")
        if not T:
            continue
        clean = [{k: x for k, x in t.items() if not k.startswith("_") and k not in ("size_why", "size_mult")} for t in T]
        S = rl.score(clean, [d for d in F.SESS if d >= "2026-01-01"])
        a = v["2026"]
        rl.save(f"lit_robust_{tid}", f"LIT robustness: {v['label']} (median copy)", "other",
                "Competitor-features #12: how much of the live LIT's 2026 money survives noisy prices, slippage, missed "
                "trades and a late entry?",
                params={**P, "robust": v["cfg"]}, trades=clean, scored=S, status="info",
                verdict=(f"{v['reps']} copies: keeps {a['keep']}% of the 2026 $ (p10 {a['keep_p10']}%, p90 {a['keep_p90']}%), PF "
                         f"{a['pf']} ({a['pf_p10']}-{a['pf_p90']}), 2-week pass/fail {a['p10']}/{a['f10']}% "
                         f"(range {a['p10_lo']}-{a['p10_hi']} / {a['f10_lo']}-{a['f10_hi']}); H1 keeps {v['H1']['keep']}%, H2 "
                         f"{v['H2']['keep']}%. Live: 2026 {base['2026']['net']:+,} PF {base['2026']['pf']}. The stored trades are "
                         "the median copy."),
                notes="tools/lit_robust.py on live_model.json lit (2026 window from 2025-10-01, LIT size rule); research/lab/robust.json.",
                writeup="lit-robust", tags=["lit", "robust"])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
