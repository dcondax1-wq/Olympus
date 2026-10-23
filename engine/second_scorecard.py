"""Go / no-go scorecard for the second strategies and account B (owner 2026-10-22, pre-launch job 2). Read-only.

Question: after N paper trades, does a second strategy still look like its backtest, or should it not go live?

Bands (build(), research/second/scorecard.json, rebuilt only when the research trades change):
  expected   bootstrap of the strategy's 2026 H2 trades (the untouched check half; research/second/*_best.json, R per
             micro after costs, $ at $500 risk a trade = the paper ledger's size): for N = 1..40 trades, 4,000 resampled
             paths -> quantiles of the cumulative R, win rate, profit factor and $.
  bad year   the same bootstrap of its 2025 trades (a pessimistic band: the year account B evals mostly died).
  account B  EMA + MACD + S/R pooled (their paper ledgers together).
Verdict on the live paper ledger (cloud state "second" ledgers, plus the PC heartbeat's finished trades the cloud does
not have yet), on the finished trades' cumulative R after n trades:
  n < 5                                   "collecting (n/20)"
  cumulative R under the expected p5      "below range: don't go live"   (worse than 19 in 20 expected paths)
  5 <= n < 20, inside (or 20+ at p5-p10)  "on track (pXX)"               XX = where it sits in the expected band
  n >= 20 and at or above the expected p10 "ready: 20+ trades inside the range"
The bad-year band is shown next to it ("like 2025" when the result is under the 2025 median): a strategy that only
matches its bad year is not a reason to buy an account.

    python -X utf8 -m engine.second_scorecard build     # -> research/second/scorecard.json (~5 s)
    python -X utf8 -m engine.second_scorecard show      # verdicts on the current cloud state (data/cloud_state.json if any)
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "second", "scorecard.json")
KEYS = {"ema_lon_vix": "ema_best.json", "macd_sweep": "md_best.json", "sr_nyreclaim": "sr_best.json"}
ACCT_B = "account_b"
SPANS = {"expected": ("2026-07-01", "2026-12-31"), "bad_year": ("2025-01-01", "2025-12-31")}
NMAX, DRAWS, SEED = 40, 4000, 20261022
READY_N, MIN_N, LOW_Q, READY_Q = 20, 5, 5, 10
QS = list(range(0, 101, 5))                 # stored quantiles of the cumulative R (for the percentile of a live result)
VERSION = 1


# ================================================================================================ bands
def _pool(fn, span):
    d = json.load(open(os.path.join(ROOT, "research", "second", fn), encoding="utf-8"))
    a, z = span
    return [(float(t["r"]), float(t["pnl_usd"])) for t in d["trades"] if a <= t["day"] <= z]


def _band(pool, seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    R = np.array([p[0] for p in pool]); U = np.array([p[1] for p in pool])
    out = {"n_pool": len(pool), "mean_r": round(float(R.mean()), 3) if len(R) else None,
           "win": round(100.0 * float((R > 0).mean()), 1) if len(R) else None, "by_n": {}}
    if not len(R):
        return out
    idx = rng.integers(0, len(R), size=(DRAWS, NMAX))
    r, u = R[idx], U[idx]
    cr, cu = np.cumsum(r, axis=1), np.cumsum(u, axis=1)
    wins = np.cumsum(r > 0, axis=1)
    gp, gl = np.cumsum(np.where(r > 0, r, 0.0), axis=1), np.cumsum(np.where(r < 0, -r, 0.0), axis=1)
    pf = np.where(gl > 0, gp / np.maximum(gl, 1e-12), 99.0)
    for n in range(1, NMAX + 1):
        k = n - 1
        q = lambda x, p: round(float(np.percentile(x[:, k], p)), 2)
        out["by_n"][str(n)] = {"cum_r_q": [q(cr, p) for p in QS], "usd": [q(cu, p) for p in (10, 50, 90)],
                               "win": [round(100.0 * float(np.percentile(wins[:, k] / n, p)), 1) for p in (10, 50, 90)],
                               "pf": [q(np.minimum(pf, 99.0), p) for p in (10, 50, 90)]}
    return out


def build(path: str = OUT) -> dict:
    out = {"version": VERSION, "nmax": NMAX, "draws": DRAWS, "ready_n": READY_N, "min_n": MIN_N, "low_q": LOW_Q, "qs": QS,
           "spans": SPANS, "bands": {}, "note": "R per micro after costs; $ at $500 risk a trade (the paper ledger's size)"}
    pools = {k: {nm: _pool(fn, sp) for nm, sp in SPANS.items()} for k, fn in KEYS.items()}
    pools[ACCT_B] = {nm: [p for k in KEYS for p in pools[k][nm]] for nm in SPANS}
    for i, (k, P) in enumerate(pools.items()):
        out["bands"][k] = {nm: _band(P[nm], SEED + 17 * i + j) for j, nm in enumerate(SPANS)}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


_CACHE = {}


def load(path: str = OUT) -> dict | None:
    try:
        m = os.path.getmtime(path)
        if _CACHE.get("m") != (path, m):
            with open(path, encoding="utf-8") as fh:
                _CACHE.update(m=(path, m), d=json.load(fh))
        return _CACHE["d"]
    except Exception:
        return None


# ================================================================================================ verdicts
def _pct(qv, x):
    """Where x sits in the stored quantiles (0-100, linear between them)."""
    if x <= qv[0]:
        return 0.0
    if x >= qv[-1]:
        return 100.0
    for i in range(1, len(qv)):
        if x <= qv[i]:
            a, b = qv[i - 1], qv[i]
            f = 0.0 if b == a else (x - a) / (b - a)
            return QS[i - 1] + f * (QS[i] - QS[i - 1])
    return 100.0


def finished(rows) -> list:
    """Finished paper trades (exit kind set, not OPEN) in entry order, one per entry time."""
    seen, out = set(), []
    for t in sorted((r for r in rows or [] if isinstance(r, dict)), key=lambda r: r.get("entry_t") or 0):
        if t.get("exit_kind") in (None, "OPEN", "") or t.get("r") is None or t.get("entry_t") is None:
            continue
        k = int(t["entry_t"])
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def verdict(band: dict | None, rows, ready_n: int = READY_N, min_n: int = MIN_N, low_q: float = LOW_Q) -> dict:
    """band = load()["bands"][key]; rows = paper trades (any order, open ones ignored). Returns the card for the page."""
    T = finished(rows)
    n = len(T)
    cum = round(sum(float(t["r"]) for t in T), 2)
    usd = round(sum(float(t.get("usd") or 0.0) for t in T), 2)
    wins = sum(1 for t in T if float(t["r"]) > 0)
    gp = sum(float(t["r"]) for t in T if float(t["r"]) > 0)
    gl = -sum(float(t["r"]) for t in T if float(t["r"]) < 0)
    out = {"n": n, "need": ready_n, "cum_r": cum, "usd": usd, "win": round(100.0 * wins / n, 1) if n else None,
           "pf": round(gp / gl, 2) if gl > 0 else (None if not n else 99.0), "pct": None, "kind": "collecting",
           "text": f"collecting ({n}/{ready_n})", "expected": None, "bad_year": None, "like_2025": None}
    if not band or not (band.get("expected") or {}).get("by_n"):
        out["text"] += " · no band (run python -m engine.second_scorecard build)"
        return out
    nb = max(1, min(n, len((band["expected"]["by_n"]))))
    E = band["expected"]["by_n"][str(nb)]
    B = ((band.get("bad_year") or {}).get("by_n") or {}).get(str(nb))
    qi = lambda p: QS.index(p)
    out["expected"] = {"at_n": nb, "cum_r": [E["cum_r_q"][qi(p)] for p in (5, 10, 50, 90)], "usd": E["usd"], "win": E["win"], "pf": E["pf"]}
    if B:
        out["bad_year"] = {"at_n": nb, "cum_r": [B["cum_r_q"][qi(p)] for p in (10, 50, 90)], "usd": B["usd"], "win": B["win"], "pf": B["pf"]}
    if n == 0:
        return out
    pct = round(_pct(E["cum_r_q"], cum))
    out["pct"] = pct
    if B:
        out["like_2025"] = cum < B["cum_r_q"][qi(50)]
    if n < min_n:
        return out
    if cum < E["cum_r_q"][qi(low_q)]:
        out.update(kind="below", text="below range: don't go live")
    elif n < ready_n or cum < E["cum_r_q"][qi(READY_Q)]:
        # under 20 trades, or 20+ but only in the bottom tenth (p5-p10): keep collecting
        out.update(kind="on_track", text=f"on track (p{pct})")
    else:
        out.update(kind="ready", text=f"ready: {ready_n}+ trades inside the range")
    return out


def merge_rows(ledger_rows, pc_rows) -> list:
    """The cloud paper ledger + the PC's finished trades it does not have yet (same entry time = the same trade)."""
    have = {int(r["entry_t"]) for r in ledger_rows or [] if isinstance(r, dict) and r.get("entry_t") is not None}
    extra = [r for r in pc_rows or [] if isinstance(r, dict) and r.get("entry_t") is not None and int(r["entry_t"]) not in have]
    return list(ledger_rows or []) + extra


def card(rows_by_key: dict, keys_b=None, bands: dict | None = None, source: str | None = None) -> dict:
    """{"strategies": {key: verdict}, "account_b": verdict over the pooled trades of keys_b, "rule": text}."""
    bands = bands if bands is not None else (load() or {})
    B = bands.get("bands") or {}
    keys_b = list(keys_b or KEYS)
    out = {"strategies": {}, "source": source, "rule": RULE, "built": bool(B)}
    for k, rows in (rows_by_key or {}).items():
        if k in KEYS:
            out["strategies"][k] = verdict(B.get(k), rows)
    pooled = [r for k in keys_b for r in finished((rows_by_key or {}).get(k))]
    out["account_b"] = ab = verdict(B.get(ACCT_B), pooled)
    ab["keys"] = keys_b
    low = [k for k in keys_b if (out["strategies"].get(k) or {}).get("kind") == "below"]
    if low and ab["kind"] in ("on_track", "ready", "collecting"):
        # account B trades all of them: one strategy under its own range blocks the account too
        ab.update(kind="below", text=f"below range: don't go live ({', '.join(low)} under its range)")
    return out


RULE = (f"Go live only after {READY_N}+ finished paper trades whose cumulative R sits inside the expected range (the 2026 H2 "
        f"bootstrap, at or above its p{READY_Q}); under its p{LOW_Q} = don't go live. Under {MIN_N} trades nothing is judged.")


def readme_lines(sc: dict | None, labels: dict | None = None) -> list:
    if not sc:
        return []
    labels = labels or {}
    L = ["", "### Go / no-go scorecard", RULE, "", "| | Trades | Cum R | Paper $ | Verdict | Expected cum R (p10-p90) | 2025-like (p50) |",
         "|---|---:|---:|---:|---|---|---|"]
    rows = list((sc.get("strategies") or {}).items()) + [("ATLAS (EMA + MACD + S/R)", sc.get("account_b") or {})]
    for k, v in rows:
        e, b = v.get("expected") or {}, v.get("bad_year") or {}
        er = f"{e['cum_r'][1]:+.1f} to {e['cum_r'][3]:+.1f}R" if e.get("cum_r") and v.get("n") else "-"
        br = f"{b['cum_r'][1]:+.1f}R" if b.get("cum_r") and v.get("n") else "-"
        L.append(f"| {labels.get(k, k)} | {v.get('n', 0)} | {float(v.get('cum_r') or 0):+.2f}R | {float(v.get('usd') or 0):+,.0f} | {v.get('text')} | {er} | {br} |")
    return L


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        o = build()
        for k, b in o["bands"].items():
            e = b["expected"]["by_n"]["20"]
            print(k, "pool", b["expected"]["n_pool"], "/", b["bad_year"]["n_pool"], "| after 20: cum R p5/p50/p90",
                  e["cum_r_q"][1], e["cum_r_q"][10], e["cum_r_q"][18], "| 2025 p50", b["bad_year"]["by_n"]["20"]["cum_r_q"][10])
    else:
        p = os.path.join(ROOT, "data", "cloud_state.json")
        st = json.load(open(p, encoding="utf-8")).get("second") if os.path.exists(p) else {}
        rows = {k: list(((st or {}).get("strategies") or {}).get(k, {}).get("ledger", {}).values()) for k in KEYS}
        print(json.dumps(card(rows), indent=1)[:3000])
