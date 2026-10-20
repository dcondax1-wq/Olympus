"""Golden numbers: the live LIT config's results must not drift silently.

tests/golden/lit_live.json freezes what the live settings (live_model.json "lit" + "lit_sizing") make, with costs:
  * LIT size rule (engine/lit.py run_x = run lit_live): 2026 H1 / H2 / 2026 / 2021-25 trades, trades a week, win %, PF, net $,
    max DD, $ a month, 2-week pass / fail (p10 / f10)
  * eval path (two_week sizing, = run lit_adopt_t15_be_off_eval): H1 / H2 trades, PF, net $, p10 / f10 and the Monte Carlo
    p10 / f10
  * a fingerprint of every trade (day, entry time, exit, $), the live params and the data file the numbers came from

Three layers, each prints a clear diff when it fails:
  1. config   live_model.json "lit" / "lit_sizing" == the golden params (a switch flipped without a new golden = FAIL)
  2. stored   research/runs/lit_live.json and lit_adopt_t15_be_off_eval.json still carry the golden numbers (a re-save that
              moved them = FAIL)
  3. engine   the engine replayed now (tools/lit_final.run on the live params; ~8 s when the LIT candidate cache
              research/runs/_cache/litfinal_*.pkl exists, the runlib cache) reproduces the golden trades and numbers.
              Without the cache this layer is SKIPPED in the fast mode (--full builds it: a few minutes).

  python -X utf8 -m tests.test_golden            # fast: layers 1-2 always, 3 when the cache exists
  python -X utf8 -m tests.test_golden --full     # layer 3 always (builds the candidate cache if missing)
  python -X utf8 -m tests.test_golden --update   # an intended change: recompute and rewrite the golden file (prints the diff)
After an intended engine / config change: rerun `python tools/lit_losses.py live` (run lit_live) and
`python -X utf8 tools/lit_adopt_combo.py save` (the eval-path run), then `--update`, and commit the new golden with the change.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
GOLDEN = os.path.join(ROOT, "tests", "golden", "lit_live.json")
RUN_LIVE, RUN_EVAL = "lit_live", "lit_adopt_t15_be_off_eval"
LIT_KEYS = ("n", "tpw", "win", "pf", "net", "dd", "per_month", "p10", "f10")
EVAL_KEYS = ("n", "pf", "net", "dd", "p10", "f10", "mc_p10", "mc_f10")
SPANS = ("H1", "H2", "2026", "2021-25")
TOL = {"net": 1.0, "dd": 1.0, "per_month": 1.0, "pf": 0.006, "tpw": 0.006, "win": 0.051, "p10": 0.051, "f10": 0.051,
       "mc_p10": 0.051, "mc_f10": 0.051, "n": 0}
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"\n{detail}" if detail and not cond else ""))


def skip(name, why):
    print(f"[SKIP] {name}: {why}")


def _lm():
    with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
        return json.load(fh)


def fingerprint(rows) -> dict:
    """rows: (day, entry_t, exit, pnl) tuples in entry order."""
    keys = [f"{d}|{int(t)}|{x}|{round(float(p), 2):.2f}" for d, t, x, p in rows]
    return {"n": len(keys), "sha1": hashlib.sha1("\n".join(keys).encode()).hexdigest()[:16],
            "n_2026": sum(1 for k in keys if k >= "2026")}


def diff(name, got: dict, want: dict, keys) -> list:
    """Lines 'name.key: golden X, now Y' for every key outside its tolerance."""
    out = []
    for k in keys:
        a, b = want.get(k), got.get(k)
        if a is None and b is None:
            continue
        if a is None or b is None or abs(float(a) - float(b)) > TOL.get(k, 1e-9):
            out.append(f"    {name}.{k}: golden {a}, now {b}")
    return out


def data_key() -> str:
    from tools import runlib as rl
    return rl._data_key()


def candidate_cache() -> str:
    from engine import lit
    from tools import lit_final as F
    P = {**lit.DEFAULTS, **_lm()["lit"]}
    return os.path.join(F.CACHE, f"litfinal_{F.CAND_V}_{P['ref']}_{'-'.join(P['extra_boxes']) or 'none'}_{data_key().replace(':', '_')}.pkl")


# ------------------------------------------------------------------------------------------------ compute
def compute() -> dict:
    """The live config replayed now: LIT size rule numbers, eval-path numbers, trade fingerprint."""
    from engine import lit
    from tools import lit_adopt_combo as AC
    from tools import lit_big_ideas as BI
    from tools import lit_final as F
    lm = _lm()
    T = sorted(F.run({**lit.DEFAULTS, **lm["lit"]}), key=lambda t: t["entry_t"])
    o = F.score(T)
    e = BI.short(BI.score(AC.units(T)))
    return {"lit_rule": {s: {k: o[s].get(k) for k in LIT_KEYS} for s in SPANS},
            "eval_path": {s: {k: e[s].get(k) for k in EVAL_KEYS} for s in ("H1", "H2")},
            "trades": fingerprint([(t["day"], t["entry_t"], t["exit"], t["pnl"]) for t in T])}


def stored() -> dict:
    """The numbers the stored runs carry (research/runs/lit_live.json + the eval-path run)."""
    from tools import lit_final as F
    from tools import runlib as rl
    r = rl.load(RUN_LIVE)
    c = r["trade_cols"]
    T = [dict(zip(c, row)) for row in r["trades"]]
    T.sort(key=lambda t: t["entry_t"])
    o = F.score(T)
    ev = rl.load(RUN_EVAL)
    return {"lit_rule": {s: {k: o[s].get(k) for k in LIT_KEYS} for s in SPANS},
            "spans_2026": {k: r["spans"]["2026"].get(k) for k in LIT_KEYS},
            "trades": fingerprint([(t["day"], t["entry_t"], t["exit"], t["pnl"]) for t in T]),
            "eval_verdict": ev.get("verdict", ""), "params": r.get("params")}


def build_golden() -> dict:
    lm = _lm()
    C = compute()
    return {"note": "frozen by tests/test_golden.py --update; see its doc for when to update",
            "data_key": data_key(), "params_lit": lm["lit"], "params_lit_sizing": lm["lit_sizing"], **C}


# ------------------------------------------------------------------------------------------------ the checks
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    full, update = "--full" in argv, "--update" in argv
    if update:
        old = json.load(open(GOLDEN, encoding="utf-8")) if os.path.exists(GOLDEN) else {}
        new = build_golden()
        lines = []
        for sec, keys in (("lit_rule", LIT_KEYS), ("eval_path", EVAL_KEYS)):
            for s in new[sec]:
                lines += diff(f"{sec}.{s}", new[sec][s], (old.get(sec) or {}).get(s) or {}, keys)
        if old.get("trades") != new["trades"]:
            lines.append(f"    trades: golden {old.get('trades')}, now {new['trades']}")
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, "w", encoding="utf-8") as fh:
            json.dump(new, fh, indent=1, sort_keys=False)
            fh.write("\n")
        print("golden updated -> tests/golden/lit_live.json" + ("\n" + "\n".join(lines) if lines else " (no number moved)"))
        return 0
    if not os.path.exists(GOLDEN):
        print("no golden file: run python -X utf8 -m tests.test_golden --update")
        return 1
    G = json.load(open(GOLDEN, encoding="utf-8"))
    lm = _lm()

    # 1. config
    dk = [k for k in sorted(set(G["params_lit"]) | set(lm["lit"])) if G["params_lit"].get(k) != lm["lit"].get(k)]
    check("config: live_model.json lit == the golden params", not dk,
          "\n".join(f"    lit.{k}: golden {G['params_lit'].get(k)!r}, now {lm['lit'].get(k)!r}" for k in dk)
          + "\n    a switch moved: rerun the runs (tools/lit_losses.py live, tools/lit_adopt_combo.py save), then --update")
    ds = [k for k in sorted(set(G["params_lit_sizing"]) | set(lm["lit_sizing"])) if G["params_lit_sizing"].get(k) != lm["lit_sizing"].get(k)]
    check("config: live_model.json lit_sizing == the golden sizing", not ds,
          "\n".join(f"    lit_sizing.{k}: golden {G['params_lit_sizing'].get(k)!r}, now {lm['lit_sizing'].get(k)!r}" for k in ds))
    dkey = data_key()
    if dkey != G.get("data_key"):
        print(f"[NOTE] data/NQ_5m.csv changed since the golden (key {G.get('data_key')} -> {dkey}): new bars move the numbers; "
              "if that is the new export, rerun the runs and --update")

    # 2. stored runs
    S = stored()
    lines = []
    for s in SPANS:
        # the stored trades carry no intraday low, so the eval odds are checked on the run's own spans below
        lines += diff(f"{RUN_LIVE}.{s}", S["lit_rule"][s], G["lit_rule"][s], ("n", "tpw", "win", "pf", "net", "dd", "per_month"))
    check(f"stored: run {RUN_LIVE} trade $ (H1 / H2 / 2026 / 2021-25) == golden", not lines, "\n".join(lines))
    lines = diff(f"{RUN_LIVE}.spans.2026", S["spans_2026"], {k: G["lit_rule"]["2026"].get(k) for k in LIT_KEYS},
                 ("n", "pf", "net", "dd", "p10", "f10"))
    check(f"stored: run {RUN_LIVE} headline spans 2026 (incl. p10 / f10) == golden", not lines, "\n".join(lines))
    check(f"stored: run {RUN_LIVE} trades == golden fingerprint", S["trades"] == G["trades"],
          f"    golden {G['trades']}\n    now    {S['trades']}")
    v = S["eval_verdict"]
    want = []
    for s in ("H1", "H2"):
        e = G["eval_path"][s]
        want += [f"PF {e['pf']} net {e['net']:+,}", f"pass/fail {e['p10']}/{e['f10']} (Monte Carlo {e['mc_p10']}/{e['mc_f10']})"]
    miss = [w for w in want if w not in v]
    check(f"stored: run {RUN_EVAL} verdict carries the golden eval-path numbers", not miss,
          "    missing in the verdict: " + "; ".join(miss) + f"\n    verdict: {v[:400]}")

    # 3. engine
    cache = candidate_cache()
    if not os.path.exists(cache) and not full:
        skip("engine: replay of the live config", f"no candidate cache ({os.path.relpath(cache, ROOT)}); run with --full to build it")
    else:
        C = compute()
        lines = []
        for s in SPANS:
            lines += diff(f"lit_rule.{s}", C["lit_rule"][s], G["lit_rule"][s], LIT_KEYS)
        check("engine: LIT size rule H1 / H2 / 2026 / 2021-25 == golden", not lines, "\n".join(lines))
        lines = []
        for s in ("H1", "H2"):
            lines += diff(f"eval_path.{s}", C["eval_path"][s], G["eval_path"][s], EVAL_KEYS)
        check("engine: eval path (two_week) H1 / H2 incl. p10 / f10 == golden", not lines, "\n".join(lines))
        check("engine: every trade == golden fingerprint", C["trades"] == G["trades"],
              f"    golden {G['trades']}\n    now    {C['trades']}\n    an engine change moved trades: if intended, --update")
    print(f"golden: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
