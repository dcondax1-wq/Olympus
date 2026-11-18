"""ZEUS Lab LIT ideas (night-labx 2026-11-18, research/writeups/zeus-lab-lit-ideas-2026-11-18.md). RESEARCH ONLY.

New Zlarior (LIT) ideas that the rule language of engine/learn_loop (one fact per step) and the tools/lit_edge "x" options
cannot express. Each is ONE pre-declared version (no grid: every cell counts against the Lab's many-tests bar). The Lab kind is
`lit_idea` (tools/zeus_lab.py): {"idea": {"name": <IDEAS key>, ...params}}.

How it is measured (nothing re-implemented): the live LIT trades of run lit_live (tools/lit_edge.ctx()["T"]) are re-walked after
the fill by `manage_x` below = tools/lit_edge.manage with every option off (checked: `check()` gives the same exit and points
for all 631 trades) + the new exit options; size ideas give a multiplier m per trade. tools/lit_edge.evaluate(U=...) then scores
the LIT size rule, the live two_week eval path and the eval odds, costs in, exactly like every other Lab LIT experiment.
Decisions use closed bars only and act at the next bar's open (- 1 tick), like the 15-minute check.

Exit ideas (post-fill):
  time_stop    {"min": 60, "r": 1.0}    `min` minutes after the fill the trade never reached +r R (so no breakeven yet) -> out.
  ny_open      {"mode": "out"}           a trade filled before 09:29 ET, still open and not yet at breakeven -> out at the open of
                                         the last bar that starts before 09:29 (1m: the 09:28 close decides, out at 09:28/09:29).
               {"mode": "be", "r": 0.5}  same moment: not at breakeven but closed >= +0.5R -> stop to entry + 1.25 (breakeven).
  news_out     {"before": 2}             a trade not yet at breakeven is closed 2 minutes before a high-impact US release
                                         (data/news/events.csv: CPI, jobs, PPI, FOMC; 2021-23 has FOMC only).
               {"before": 2, "mode": "be", "r": 0.5}  same moment: not at breakeven but closed >= +0.5R -> stop to breakeven.
  stall        {"min": 60}               once at breakeven, 60 minutes without a new best price -> out.
  be_close     {}                        breakeven moves on a 1m (5m) CLOSE at +1R instead of the first touch.
Size ideas (x m, the Lab's tilt machinery: one rounding with the weekly stop, eval caps after it):
  nr7          {"mult": 1.25}            the session before was the narrowest of the last 7 (Crabel NR7) -> x1.25.
  bu_london    {"mult": 1.25}            the swept level is a build-up (equal highs / lows) AND the entry is in London 02:00-08:00.
  stagger      {"mult": 0.5}             (night-litplus 2026-11-18, two evals on the same signals) the 50K's side of "alternate":
                                         every 2nd LIT signal (entry order) at x0.5, the others unchanged. The pair view (the 25K
                                         takes the other half) is tools/money/lit_two_evals.py.
Eval ideas (the trades and the LIT size rule unchanged; only the eval sizing moves; night-litplus 2026-11-18):
  last_bullet  {"share": 0.8, "give_up": 200}   ATLAS's zombie-eval rule (engine/account_b.last_bullet + dll_guard, eval
                                         give-up) on Zlarior's eval: a 0 from the room share -> 1 micro when its full stop-out fits
                                         share x the room; an eval under give_up $ of room after a session is given up (= a fail).
                                         Applied to the Lab's eval path through eval_hook(); the two live evals together:
                                         tools/money/lit_two_evals.py.

    python -X utf8 tools/lit_lab_ideas.py check    # options off == the live trades (exit + points, every trade)
"""
from __future__ import annotations

import csv
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

NEWS = os.path.join(ROOT, "data", "news", "events.csv")
NY_CUT = 569                                   # 09:29 ET (minute of the day)
EXIT_IDEAS = ("time_stop", "ny_open", "news_out", "stall", "be_close")
SIZE_IDEAS = ("nr7", "bu_london", "stagger")
EVAL_IDEAS = ("last_bullet",)
IDEAS = EXIT_IDEAS + SIZE_IDEAS + EVAL_IDEAS
LONDON = ("London 02-05", "London late 05-08")


def idea_errors(o) -> list:
    if not isinstance(o, dict) or o.get("name") not in IDEAS:
        return [f"idea must be a dict with name in {IDEAS}"]
    n = o["name"]
    if n == "time_stop" and not (float(o.get("min", 0)) > 15 and 0 < float(o.get("r", 0)) <= 3):
        return ["time_stop needs min > 15 and 0 < r <= 3"]
    if n == "news_out" and o.get("mode", "out") not in ("out", "be"):
        return ["news_out mode must be out or be"]
    if n == "ny_open" and o.get("mode") not in ("out", "be"):
        return ["ny_open mode must be out or be"]
    if n in SIZE_IDEAS and not (0 <= float(o.get("mult", -1)) <= 1.5):
        return ["mult must be 0..1.5"]
    if n == "stagger" and not (0 < float(o.get("mult", -1)) < 1):
        return ["stagger mult must be between 0 and 1"]
    if n == "last_bullet" and not (0 < float(o.get("share", -1)) <= 1 and float(o.get("give_up", 0) or 0) >= 0):
        return ["last_bullet needs 0 < share <= 1 and give_up >= 0"]
    return []


_N = {}


def news_minutes() -> dict:
    """day -> sorted ET minutes of the high-impact releases."""
    if not _N:
        try:
            with open(NEWS, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if (r.get("impact") or "").lower() != "high":
                        continue
                    hh, mm = (r.get("time_et") or "0:0").split(":")[:2]
                    _N.setdefault(r["date"], set()).add(int(hh) * 60 + int(mm))
        except OSError:
            pass
        for k in list(_N):
            _N[k] = sorted(_N[k])
        _N.setdefault("__loaded__", [])
    return _N


def manage_x(E, o, BX, fill, d, entry, stop, tg, s_day, risk, day):
    """tools/lit_edge.manage with options off (live) + the exit idea o. Returns (exit kind, pts, worst, mfe, exit k)."""
    LIVE, BE_OFF, SLIP = E.LIVE, E.BE_OFF, E.SLIP
    B = BX.B
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LIVE["flat_mod"]
    step = B.secs // 60
    tc = LIVE.get("t_check") if B.secs == 60 else None
    be_r = LIVE["be_r"]
    name = (o or {}).get("name")
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    cut = None
    k = fill
    exit_px = kind = None
    ts_done = ny_done = False
    best_k, best_hi = fill, -1e18
    nm = [m for m in news_minutes().get(day, []) if m - int(o.get("before", 2)) > int(B.mod[fill])] if name == "news_out" else []
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if hi_d[k] >= tg:
            exit_px, kind = tg, "TARGET"; break
        if hi_d[k] > best_hi:
            best_hi, best_k = float(hi_d[k]), k
        trig = (c_d[k] if name == "be_close" else hi_d[k]) >= entry + be_r * risk
        if be_r is not None and not be_done and trig:
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
            be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
                k += 1
                continue
        nxt = k + 1 < B.n and B.day[k + 1] == s_day
        mins = round((B.t[k] - B.t[fill]) / 60.0) + step            # minutes from the fill to this bar's close
        if nxt and name == "time_stop" and not ts_done and mins >= float(o["min"]):
            ts_done = True
            if mfe < float(o["r"]):
                cut = "TIME"; k += 1; continue
        if nxt and name == "ny_open" and not ny_done and int(B.mod[fill]) < NY_CUT and int(B.mod[k + 1]) + step > NY_CUT \
                and int(B.mod[k]) < NY_CUT:
            ny_done = True
            if not be_done:
                if o["mode"] == "out":
                    cut = "NY_OPEN"; k += 1; continue
                if c_d[k] >= entry + float(o.get("r", 0.5)) * risk and entry + BE_OFF > cur:
                    cur = entry + BE_OFF
                    be_done = True
        if nxt and nm and not be_done:
            T = nm[0] - int(o.get("before", 2))
            if int(B.mod[k + 1]) + step > T >= int(B.mod[k]) + step:
                if o.get("mode", "out") == "out":
                    cut = "NEWS"; k += 1; continue
                if c_d[k] >= entry + float(o.get("r", 0.5)) * risk and entry + BE_OFF > cur:
                    cur = entry + BE_OFF
                    be_done = True
            nm = [m for m in nm if m - int(o.get("before", 2)) >= int(B.mod[k]) + step]
        if nxt and name == "stall" and be_done and (B.t[k] - B.t[best_k]) / 60.0 >= float(o.get("min", 60)):
            cut = "STALL"; k += 1; continue
        k += 1
    if exit_px is None:
        return None
    return kind, exit_px - entry, worst, mfe, k


def _nr7_days(E) -> set:
    c = E.ctx()
    M, rng = c["M"], c["rng"]
    out = set()
    for k in range(7, len(rng)):
        w = rng[k - 7:k]
        if np.isfinite(w).all() and rng[k - 1] <= w.min() + 1e-9:
            out.add(str(M.days[k][0]))
    return out


def size_fn(E, o):
    """mfn(t, intel_row) -> multiplier for the size ideas."""
    m = float(o.get("mult", 1.25))
    if o["name"] == "nr7":
        days = _nr7_days(E)
        return lambda t, r: m if str(t["day"]) in days else 1.0
    if o["name"] == "bu_london":
        return lambda t, r: m if r.get("lvl_type") == "build-up" and r.get("session") in LONDON else 1.0
    if o["name"] == "stagger":
        order = {int(t["entry_t"]): i for i, t in enumerate(sorted(E.ctx()["T"], key=lambda t: t["entry_t"]))}
        return lambda t, r: m if order[int(t["entry_t"])] % 2 == 1 else 1.0
    raise ValueError(o["name"])


def units(o: dict):
    """The re-walked live trades (tools/lit_edge.trades format) under idea o."""
    from tools import lit_edge as E
    if o["name"] in SIZE_IDEAS:
        return E.trades(mfn=size_fn(E, o))
    if o["name"] in EVAL_IDEAS:
        return E.trades({})                     # the trades do not change; eval_hook() changes the eval sizing
    c = E.ctx()
    out = []
    for t in c["T"]:
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        risk = entry - stop
        kind, pts, worst, mfe, kx = manage_x(E, o, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk, str(t["day"]))
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(B.t[kx]) + B.secs, "dir": d, "exit": kind,
                    "risk": round(risk, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4), "w1": round(worst, 4),
                    "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": t["tf"], "m": 1.0, "floored": False,
                    "live_exit": t.get("exit"), "live_pts": round((t["pnl"] + E.COMM * t["qty"]) / (E.PV * t["qty"]), 4)})
    return out


def hits(o: dict, U, U0) -> dict:
    """Trades the idea touched per span (exit ideas: exit or points changed; size ideas: m != 1; eval ideas: eval-path
    trades whose micros changed or that were added / dropped, on the back-to-back 2-week evals of each 2026 half)."""
    from engine import learn_loop as LL
    if o["name"] in EVAL_IDEAS:
        return eval_hits(o, U0)
    b = {u["entry_t"]: u for u in U0}
    out = {}
    for u in U:
        x = b.get(u["entry_t"])
        ch = abs(float(u.get("m", 1.0)) - 1.0) > 1e-9 if o["name"] in SIZE_IDEAS else \
            (x is None or x["exit"] != u["exit"] or abs(x["pts"] - u["pts"]) > 1e-6)
        if ch:
            sp = LL._span_lit(u["day"])
            out[sp] = out.get(sp, 0) + 1
    return out


# ================================================================================================ eval ideas (night-litplus)
def run_eval_zombie(seq, by, horizon=20, keep=None, cfg=None, share=None, give_up=None):
    """tools/lit_edge.run_eval_m exactly + ATLAS's zombie-eval rule: a 0 from the room share -> engine/account_b.last_bullet
    (1 micro when its full stop-out fits share x the room) + engine/account_b.dll_guard; an eval with less than give_up $ of
    room after a session is given up (FAIL). share / give_up None = run_eval_m (check())."""
    from engine import account_b as EAB
    from engine import lit
    from engine import sizing as SZ
    from tools import lit_adv_manage as A
    from tools import lit_big_ideas as BI
    PV, SLIP = lit.PV, lit.SLIP
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            m0 = lit.qty_for(t["risk"])
            tr = {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}
            m = float(t.get("m", 1.0))
            if abs(m - 1.0) > 1e-9:
                tr.update(idm_m=m, idm_cap=None, wk_m=1.0)
            r = SZ.lit_qty(m0, tr, cfg, room=st["room"], state=st, learning=None) if m0 else {"qty": 0, "reasons": []}
            q = int(r["qty"])
            if q <= 0 and share and m0:
                r2 = EAB.last_bullet(r, float(t["risk"]), float(share), st)
                if int(r2.get("qty") or 0) > 0:
                    q = int(EAB.dll_guard(r2, float(t["risk"]), {"dll": dll}, st).get("qty") or 0)
            if q <= 0:
                continue
            pnl, low, tot = BI.trade_pnl(t, q, q, st)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2)}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
        if give_up and bal - floor < float(give_up):
            return "FAIL", kk + 1
    return "OPEN", min(len(seq), horizon)


class eval_hook:
    """with eval_hook(idea): the Lab's eval path (tools/lit_adv_manage.run_eval, = tools/lit_edge.run_eval_m) runs the eval
    idea's sizing; restored on exit. Any other idea: no change."""

    def __init__(self, o):
        self.o = o or {}
        self.keep = None

    def __enter__(self):
        if self.o.get("name") in EVAL_IDEAS:
            from tools import lit_adv_manage as A
            from tools import lit_edge  # noqa: F401  (sets A.run_eval = run_eval_m first)
            self.keep = A.run_eval
            sh, gu = float(self.o.get("share", 0.8)), float(self.o.get("give_up") or 0.0) or None
            A.run_eval = lambda seq, by, horizon=20, keep=None, cfg=None: run_eval_zombie(seq, by, horizon, keep, cfg, sh, gu)
        return self

    def __exit__(self, *exc):
        if self.keep is not None:
            from tools import lit_adv_manage as A
            A.run_eval = self.keep
        return False


def eval_hits(o: dict, U0) -> dict:
    """Eval ideas: back-to-back 2-week eval trades (tools/lit_rev_exit.b2b10) whose micros changed, or that were added /
    dropped, per 2026 half."""
    from tools import lit_edge as E
    from tools import lit_rev_exit as R
    U26 = [u for u in U0 if u["day"] >= "2026"]
    out = {}
    for sp in ("H1", "H2"):
        base = {r["entry_t"]: r["qty"] for r in R.b2b10(U26, sp)[0]}
        with eval_hook(o):
            new = {r["entry_t"]: r["qty"] for r in R.b2b10(U26, sp)[0]}
        out[sp] = sum(1 for k in set(base) | set(new) if base.get(k) != new.get(k))
    E.ctx()
    return out


def check() -> int:
    """Options off (an unknown-to-manage name) == tools/lit_edge.trades({}) for every trade."""
    from tools import lit_edge as E
    U0 = E.trades({})
    c = E.ctx()
    bad = 0
    for t, u0 in zip(c["T"], U0):
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        r = manage_x(E, {}, BX, fill, d, t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d, int(B.day[fill]),
                     t["entry_px"] * d - t["stop_px"] * d, str(t["day"]))
        if r[0] != u0["exit"] or abs(round(r[1], 4) - u0["pts"]) > 1e-6:
            bad += 1
    print(f"check: {len(U0)} trades, {bad} differ from tools/lit_edge (options off)")
    # the eval-idea runner with the rule off == tools/lit_edge.run_eval_m (every start of both 2026 halves, 20 sessions)
    from tools import lit_adv_manage as A
    by = A.by_day([u for u in U0 if u["day"] >= "2026"])
    ev_bad = 0
    for sp in ("H1", "H2"):
        a, z = A.span_ix(sp)
        for i in range(a, z):
            if run_eval_zombie(list(range(i, z)), by) != E.run_eval_m(list(range(i, z)), by):
                ev_bad += 1
    print(f"check: eval runner with the zombie rule off differs on {ev_bad} eval starts")
    return 0 if bad == 0 and ev_bad == 0 else 1


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]:
        raise SystemExit(check())
    print(__doc__)
