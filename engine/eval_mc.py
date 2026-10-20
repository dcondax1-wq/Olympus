"""Live Monte Carlo of the CURRENT MFFU eval (morning brief, engine/lit_brief.morning): from today's eval state (session N,
profit, room to the trailing floor), the odds of passing / failing within the 2-week clock (session 10) and eventually.

Sample: research/lab/eval_sample.json (tools/lit_eval_sample.py): every 2026 session of the live LIT replay (run lit_live,
tools/lit_final.run on live_model.json "lit") with its trade per 1 micro {risk, tgt, pts (net of costs), w1 (worst open
pts)}; a day without a trade is an empty session. Paths are 5-session blocks drawn from 2026 (and from H2 2026 alone,
the check half: quote that one); each trade is sized by engine/sizing.lit_qty exactly as the live loop does (lit_sizing
of live_model.json: two_week to session 10, then after_mode), with the MFFU Builder 50K rules (target +$3,000, $2,000 EOD
trailing floor locking at +$100, $1,000 soft daily loss). Read-only: never changes a size or an order.

    from engine import eval_mc
    mc = eval_mc.from_clock(state["eval_2wk"], lm["lit_sizing"])     # None when the clock is unknown / not open
    python -X utf8 -m engine.eval_mc [session profit room]           # print one run
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "research", "lab", "eval_sample.json")
PV = 2.0
SLIP = 0.25
N_PATHS = 2000
HORIZON = 60          # sessions simulated after today (eventual = within ~3 months)
BLOCK = 5
_S = {}


def sample(path=SAMPLE):
    if path not in _S:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        by = {}
        for t in d["trades"]:
            by.setdefault(t["day"], []).append(t)
        d["by"] = [by.get(s, []) for s in d["sess"]]
        _S[path] = d
    return _S[path]


def _cfg(lit_sizing):
    from engine import sizing as SZ  # noqa: F401
    c = dict(lit_sizing or {})
    c.setdefault("mode", "two_week")
    return c


def play(cfg, seq, by, session0, profit, floor, peak, rules=None, days=None):
    """One path from today's state: ("PASS" | "FAIL" | "OPEN", eval session it ended on). days = the sample's session dates
    (the eval weekly loss stop lit_sizing.wk_loss_usd needs the calendar week; a path's k-th session counts as week k // 5)."""
    from engine import sizing as SZ
    from engine.lit import qty_for
    A = {**SZ.TW_50K, **(rules or {})}
    tgt, mll, dll, lock = float(A["target"]), float(A["mll"]), float(A["dll"]), float(A["lock"])
    bal = float(profit)
    wk_pnl = {}
    for k, si in enumerate(seq):
        sess = session0 + k
        cum = 0.0
        wk = k // 5
        for j, t in enumerate(by[si]):
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": sess, "n_today": j, "wk_pnl": wk_pnl.get(wk, 0.0) + cum}
            m0 = int(t["q"]) if "q" in t else qty_for(t["risk"])        # the model's micros (weekly stop, idm_size) as live
            tr = {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": t.get("sm", 1.0),
                  **{k: t[k] for k in ("idm_m", "idm_cap", "wk_m") if k in t}}
            q = SZ.lit_qty(m0, tr, cfg, room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl = t["pts"] * PV * q
            low = min(0.0, t["w1"] * PV * q, pnl)
            if cum + low <= -dll:                     # the soft daily loss closes the trade
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if bal + cum + low <= floor:
                return "FAIL", sess
            cum += pnl
        bal += cum
        wk_pnl[wk] = wk_pnl.get(wk, 0.0) + cum
        if bal <= floor:
            return "FAIL", sess
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lock)
        if bal >= tgt:
            return "PASS", sess
    return "OPEN", session0 + len(seq) - 1


def _seqs(ix, n, length, rng):
    out = []
    a, z = ix[0], ix[-1] + 1
    for _ in range(n):
        s = []
        while len(s) < length:
            b = int(rng.integers(a, max(a + 1, z - BLOCK + 1)))
            s.extend(range(b, min(z, b + BLOCK)))
        out.append(s[:length])
    return out


def simulate(session, profit, room, lit_sizing=None, n=N_PATHS, horizon=HORIZON, seed=None, span="2026", rules=None, D=None):
    """Odds from today's state. session = today's eval session (1 = first), profit = closed eval P&L before today, room =
    profit - trailing floor. Returns {p10, f10, pass, fail, open, pass_med, n, span, ...} in % / sessions."""
    from engine import sizing as SZ
    A = {**SZ.TW_50K, **(rules or {})}
    D = D or sample()
    if "by" not in D:
        by = {}
        for t in D["trades"]:
            by.setdefault(t["day"], []).append(t)
        D = {**D, "by": [by.get(s, []) for s in D["sess"]]}
    lim = int(getattr(SZ, "EVAL_SESSIONS", 10))
    floor = float(profit) - float(room)
    peak = max(float(profit), floor + float(A["mll"])) if floor < float(A["lock"]) else float(profit)
    cfg = _cfg(lit_sizing)
    a, z = {"2026": ("2026-01-01", "2026-12-31"), "H2": ("2026-07-01", "2026-12-31"), "H1": ("2026-01-01", "2026-06-30")}[span]
    ix = [i for i, d in enumerate(D["sess"]) if a <= d <= z]
    rng = np.random.default_rng(seed if seed is not None else 11)
    res = [play(cfg, s, D["by"], int(session), float(profit), floor, peak, rules) for s in _seqs(ix, n, horizon, rng)]
    P = [d for r, d in res if r == "PASS"]
    F = [d for r, d in res if r == "FAIL"]
    pct = lambda x: round(100.0 * x / len(res), 1)  # noqa: E731
    return {"span": span, "n": len(res), "session": int(session), "limit": lim, "horizon": horizon,
            "p10": pct(sum(1 for d in P if d <= lim)), "f10": pct(sum(1 for d in F if d <= lim)),
            "pass": pct(len(P)), "fail": pct(len(F)), "open": pct(len(res) - len(P) - len(F)),
            "pass_med": float(np.median(P)) if P else None, "sessions_in_sample": len(ix)}


def from_clock(clock, lit_sizing=None, n=N_PATHS, seed=None):
    """The brief's block from state["eval_2wk"] (engine/sizing.eval_clock): None unless the eval is open."""
    ck = clock or {}
    if ck.get("status") != "open" or ck.get("session") is None or ck.get("room") is None:
        return None
    sess = int(ck["session"])
    # the morning brief runs before today's trades: profit before today = clock profit (closed P&L incl. today's, 0 at 01:30)
    profit, room = float(ck.get("profit") or 0.0), float(ck["room"])
    out = simulate(sess, profit, room, lit_sizing, n=n, seed=seed, span="2026")
    h2 = simulate(sess, profit, room, lit_sizing, n=n, seed=seed, span="H2")
    lim = out["limit"]
    left = max(0, lim - sess + 1)
    out["h2"] = {k: h2[k] for k in ("p10", "f10", "pass", "fail", "open", "pass_med")}
    clock_txt = (f"pass by session {lim} {h2['p10']:.0f}% / fail {h2['f10']:.0f}% ({left} sessions left), "
                 if left else f"past the 2-week clock (session {sess}), ")
    out["text"] = (f"Monte Carlo from today (session {sess}, ${profit:+,.0f}, ${room:,.0f} room; {n:,} paths of 2026 H2 sessions): "
                   f"{clock_txt}eventually pass {h2['pass']:.0f}% / fail {h2['fail']:.0f}%"
                   + (f", median pass on session {h2['pass_med']:.0f}" if h2.get("pass_med") else "")
                   + f". Whole 2026: {out['p10']:.0f}% / {out['f10']:.0f}% by session {lim}, {out['pass']:.0f}% eventually.")
    return out


if __name__ == "__main__":
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    a = [float(x) for x in sys.argv[1:4]] if len(sys.argv) >= 4 else [1, 0, 2000]
    ck = {"status": "open", "session": int(a[0]), "profit": a[1], "room": a[2]}
    print(json.dumps(from_clock(ck, lm.get("lit_sizing")), indent=1))
