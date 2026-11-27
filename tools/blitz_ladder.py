"""BLITZ readiness card + forward paper gate (day-blitzready 2026-11-27). PAPER RESEARCH ONLY.

It only COUNTS: it never arms, routes, sizes or switches anything and never touches the --blitz live switch. The gate is
written here BEFORE any forward paper trade exists and must not be loosened after seeing forward data (same rule as
tools/of_ladder.py). A passed gate only means "the owner may be ASKED about the next step (BLITZ on Sim)"; the owner's yes and
the typed phrase are always the step after.

    python -X utf8 tools/blitz_ladder.py        -> research/handoff/2026-11-27/blitz/card.json (+ card_gate.json only if the gate passed)

Backtest numbers: engine.blitz.backtest on data/NQ_1m.csv (2026, 1m, costs in: $1.90 a micro round trip, 1 tick on the entry
and on every stop / market exit; $150 a trade = at least 1 micro, as research/writeups/blitz-review-2026-11-18.md) and, for
2021-25 (5m only, the 1m history starts 2026) + the 25K eval Monte Carlo, research/scalp/blitz_review.json (cited, not rebuilt).
Forward = the PC paper lane's trade log data/blitz_paper/trades.jsonl (engine/blitz_paper.py), exit rows, from FWD_FROM.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT_DIR = os.path.join(ROOT, "research", "handoff", "2026-11-27", "blitz")
CARD = os.path.join(OUT_DIR, "card.json")
GATE_CARD = os.path.join(OUT_DIR, "card_gate.json")
REVIEW = os.path.join(ROOT, "research", "scalp", "blitz_review.json")
FWD_FROM = "2026-11-27"
USD = 150.0                                          # a trade, at least 1 micro (blitz._fixed_q)

# the forward gate (pre-registered 2026-11-27, before the first forward trade; do not loosen)
GATE = {"n": 40, "pf": 1.30, "pf_stress": 1.15, "mean_r": 0.08, "halves": 0.0, "max_dd": 1500.0, "parity": 1.0}
STOP = {"first": 15, "pf": 0.90, "sum_usd": -900.0, "dd": 1800.0}
STEPS = [
    {"step": 0, "name": "paper forward", "where": "the PC paper lane (engine/blitz_paper.py), nothing routed",
     "gate": (f"{GATE['n']} forward trades (about 6 weeks at 7 a week): PF >= {GATE['pf']} at $150 a trade with costs, PF >= "
              f"{GATE['pf_stress']} with one more tick each way, mean >= +{GATE['mean_r']}R, both halves net >= $0, max DD <= "
              f"${GATE['max_dd']:,.0f}, every trade equals a replay of the same bars (parity 100%)"),
     "stop": (f"after {STOP['first']} trades PF < {STOP['pf']} or net <= ${STOP['sum_usd']:,.0f}, or max DD > ${STOP['dd']:,.0f} at any time: "
              "BLITZ is shelved, no ask")},
    {"step": 1, "name": "Sim", "where": "BLITZ on a NinjaTrader SIMULATION account (account C route; owner yes + typed phrase)",
     "gate": "10 Sim trades, fills within 2 ticks of paper on average, 0 hedge / one-position conflicts",
     "stop": "any hedge conflict, or fills worse than paper by > 4 ticks on average"},
    {"step": 2, "name": "real money", "where": "only next to Zlarior on a funded 50K (both Builder 25K slots are used)",
     "gate": "Zlarior's 50K funded first + 2 months of step 1 with the paper sum > 0", "stop": "lane sum <= -$600 on the account"},
]


def _rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def usd_rows(rows: list, extra_ticks: float = 0.0) -> list:
    """$ of each trade at $150 a trade (>= 1 micro) with costs in; extra_ticks = more slippage each way (the stress)."""
    from engine import blitz as B
    out = []
    for r in rows:
        pm = r["pnl_pm"] - extra_ticks * 2 * B.TICK * B.PV
        out.append(B._fixed_q(r["risk_pm"], USD) * pm)
    return out


def stats(rows: list, first: str, last: str) -> dict:
    """trades / week, win %, PF, net, $ / month, max DD of backtest rows (research/scalp dicts with pnl_pm / risk_pm)."""
    import numpy as np
    if not rows:
        return {"n": 0}
    out = {}
    for tag, e in (("", 0.0), ("_stress", 1.0)):
        u = np.array(usd_rows(rows, e))
        gw, gl = u[u > 0].sum(), -u[u < 0].sum()
        eq = np.cumsum(u)
        dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
        out[f"pf{tag}"] = round(float(gw / gl), 2) if gl else None
        out[f"net{tag}"] = round(float(u.sum()))
        out[f"dd{tag}"] = round(dd)
    d0, d1 = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    months = max(1 / 21, ((d1 - d0).days + 1) / 30.4)
    weeks = max(1.0, ((d1 - d0).days + 1) / 7)
    out.update({"n": len(rows), "per_week": round(len(rows) / weeks, 1), "win": round(100 * sum(1 for r in rows if r["r"] > 0) / len(rows), 1),
                "avg_r": round(sum(r["r"] for r in rows) / len(rows), 3), "per_month": round(out["net"] / months),
                "per_month_stress": round(out["net_stress"] / months), "from": first, "to": last})
    return out


def backtest_2026() -> tuple:
    import pandas as pd
    from engine import blitz as B
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))[["time", "open", "high", "low", "close"]]
    rows = B.backtest(df)
    last = B.et_date(int(df["time"].iloc[-1]))
    return rows, last


def spans() -> dict:
    """2026 Jan-Jun / Jul-now rebuilt from the rule; 2021-25 + eval paths cited from the Nov-18 review (their H2 = Jul-Oct)."""
    rows, last = backtest_2026()
    rev = _rj(REVIEW) or {}
    sp = (rev.get("spans") or {})
    h1 = [r for r in rows if r["day"] <= "2026-06-30"]
    h2 = [r for r in rows if r["day"] > "2026-06-30"]
    out = {"H1": {"name": "2026 Jan-Jun", **stats(h1, "2026-01-01", "2026-06-30")},
           "H2": {"name": f"2026 Jul-{dt.date.fromisoformat(last):%b %d}", **stats(h2, "2026-07-01", last)}}
    r = (sp.get("R") or {})
    t, t1 = (r.get("today") or {}), (r.get("today_plus1tick") or {})
    out["R"] = {"name": "2021-25 (5m bars, no 1m before 2026)", "n": t.get("n"), "per_week": t.get("tpw"), "win": t.get("win"), "avg_r": t.get("avg_r"),
                "pf": t.get("pf"), "net": t.get("net"), "per_month": t.get("per_month"), "dd": t.get("dd"), "pf_stress": t1.get("pf"),
                "net_stress": t1.get("net"), "per_month_stress": t1.get("per_month"), "dd_stress": t1.get("dd"),
                "source": "research/scalp/blitz_review.json (account C rule, 5m)"}
    for k, nm in (("H1", "H1"), ("H2", "H2"), ("R", "R")):
        e = ((sp.get(k) or {}).get("eval")) or {}
        out[nm]["eval"] = {"pass_2wk_pct": e.get("p10"), "fail_2wk_pct": e.get("f10"), "median_sessions_to_pass": e.get("pass_med"),
                           "whole_slot_usd_month": e.get("life_pm"), "slot_loses_money_pct": e.get("life_lose"),
                           "note": "25K eval Monte Carlo at the live size, net of every $63 eval (review H2 = Jul-Oct)"}
    return out


# ------------------------------------------------------------------------------------------------ forward
def forward_rows(root: str = ROOT, since: str = FWD_FROM) -> list:
    """Closed paper trades of the lane (exit rows), oldest first, from `since`. Each row carries r_usd150 / r / usd."""
    from engine import blitz_paper as BP
    rows = [x for x in BP.read_trades(root) if x.get("ev") == "exit" and str(x.get("day") or "") >= since and not x.get("killed_window")]
    return sorted(rows, key=lambda x: int(x["entry_t"]))


def _pf(u: list):
    gw, gl = sum(x for x in u if x > 0), -sum(x for x in u if x < 0)
    return round(gw / gl, 2) if gl else (None if not gw else 99.0)


def _dd(u: list) -> float:
    eq, pk, dd = 0.0, 0.0, 0.0
    for x in u:
        eq += x
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    return round(dd)


def parity(rows: list, root: str = ROOT) -> dict:
    """Every forward paper trade vs engine.blitz.backtest on the same bars (data/NQ_1m.csv, as far as it reaches). A trade the bars do
    not cover yet is 'pending', not a miss."""
    import pandas as pd
    from engine import blitz as B
    try:
        df = pd.read_csv(os.path.join(root, "data", "NQ_1m.csv"))[["time", "open", "high", "low", "close"]]
        end = int(df["time"].iloc[-1]) + 60
        bt = {int(r["entry_t"]): r for r in B.backtest(df)}
    except Exception as e:  # noqa: BLE001
        return {"checked": 0, "pending": len(rows), "match": 0, "error": str(e)[:100]}
    chk = [r for r in rows if int(r["exit_t"] or 0) <= end]
    ok = 0
    for r in chk:
        b = bt.get(int(r["entry_t"]))
        if b and int(b["dir"]) == int(r["dir"]) and abs(float(b["entry"]) - float(r["entry"])) < 0.01 and abs(float(b["exit"]) - float(r["exit"])) < 0.01 \
                and str(b["exit_kind"]) == str(r["exit_kind"]):
            ok += 1
    return {"checked": len(chk), "match": ok, "pending": len(rows) - len(chk)}


def score(rows: list, par: dict | None = None) -> dict:
    """The gate on the forward rows (PF / R after costs, $150 a trade; stress = one more tick each way per micro)."""
    u = [float(r.get("r_usd150") or 0) for r in rows]
    rr = [float(r.get("r") or 0) for r in rows]
    # one more tick each way = $1 a micro; r_usd150 rows carry the micro count only through risk, so the stress is a flat $ per micro
    from engine import blitz as B
    q = [B._fixed_q((float(r.get("risk_pts") or 1.0) + B.TICK) * B.PV + B.COMM, USD) for r in rows]
    us = [a - 1.0 * n for a, n in zip(u, q)]
    n = len(rows)
    half = n // 2
    n1, n2 = sum(u[:half]), sum(u[half:])
    par = par or {"checked": 0, "match": 0, "pending": 0}
    res = {"n": n, "net": round(sum(u)), "pf": _pf(u), "pf_stress": _pf(us), "mean_r": round(sum(rr) / n, 3) if n else None, "dd": _dd(u),
           "half1": round(n1), "half2": round(n2), "parity": par}
    stop = None
    if n >= STOP["first"] and ((res["pf"] or 0) < STOP["pf"] or sum(u) <= STOP["sum_usd"]):
        stop = f"{n} trades: PF {res['pf']}, net ${sum(u):+,.0f}"
    if n and -res["dd"] > STOP["dd"]:
        stop = f"max DD ${res['dd']:,}"
    res["stop"] = stop
    ok = (n >= GATE["n"] and (res["pf"] or 0) >= GATE["pf"] and (res["pf_stress"] or 0) >= GATE["pf_stress"] and (res["mean_r"] or 0) >= GATE["mean_r"]
          and n1 >= GATE["halves"] and n2 >= GATE["halves"] and -res["dd"] <= GATE["max_dd"]
          and par["pending"] == 0 and par["checked"] > 0 and par["match"] == par["checked"] and stop is None)
    res["passed"] = bool(ok)
    res["status"] = "shelved" if stop else "PASSED: ask the owner about Sim" if ok else f"collecting ({n}/{GATE['n']})"
    return res


def card(root: str = ROOT, write: bool = True) -> dict:
    rows = forward_rows(root)
    fwd = score(rows, parity(rows, root))
    c = {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "day": "2026-11-27", "paper_only": True,
         "what": ("BLITZ = the noise-area 1-minute scalp (engine/blitz.py): a close outside the 14-day noise band at 11:00-15:30 ET, "
                  "market entry at the next open, stop 1.5 x ATR, trail after +1R, out after 30 min / 15:55, 6 a day, only after a day "
                  "whose range was >= 0.8 x the 14-day mean"),
         "why_off": ("hidden on every dashboard by the owner's rule (dashboard_view.json hidden_bots = blitz, 2026-11-15) and no account "
                     "(both Builder 25K slots are used); the in-bot paper shadow runs but is scrubbed from the feed, so the PC feed "
                     "read 'off'. Real money is the owner's switch and stays off."),
         "spans": spans(), "gate": {"params": GATE, "stop": STOP, "steps": STEPS}, "forward": fwd,
         "verdict": ("BLITZ is a 2026 edge (PF 1.4-1.6) that was ~zero in 2021-25 (PF 1.05, 2024 negative). Paper only until the forward "
                     "gate passes; even then the next step is Sim, never an account.")}
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(CARD, "w", encoding="utf-8") as fh:
            json.dump(c, fh, indent=1, default=float)
        if fwd["passed"]:
            with open(GATE_CARD, "w", encoding="utf-8") as fh:
                json.dump({"id": "blitz-gate-sim", "q": "BLITZ passed its paper gate: put it on a Sim account?", "forward": fwd,
                           "status": "draft"}, fh, indent=1)
    return c


def main() -> int:
    c = card()
    f = c["forward"]
    print("BLITZ forward:", f["status"], f"n={f['n']} PF={f['pf']} net=${f['net']}")
    for k in ("H1", "H2", "R"):
        s = c["spans"][k]
        print(k, s.get("name"), "n", s.get("n"), "PF", s.get("pf"), "net", s.get("net"), "$/mo", s.get("per_month"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
