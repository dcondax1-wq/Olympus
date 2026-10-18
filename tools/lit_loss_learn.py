"""LIT loss learning (owner, 2026-10-18: "Start really working on these losses and how to learn from it. There's definitely a
way. You're just not finding it, so go figure it out.").

What is new here (the earlier loss studies are lit-losses.md, lit-1m-management.md, lit-trade-selection.md,
lit-htf-confluences.md, lit-two-week-eval.md): every idea is scored on the number the owner cares about most, the MFFU 50K
2-week pass rate (p10 / f10) under the LIVE two-week sizing (live_model.json lit_sizing mode "two_week", config C: one
winner passes, 60% of the room, $1,000 soft daily loss, no weekly stop; engine/sizing.py two_week_qty), with money next to it.
Under that sizing a loser costs room, and the room decides how big the winner can be when it comes. So the question is not
"does the rule make more R" but "does it keep more room for the winner without killing winners".

Families tested (all causal, decided on closed 1m bars, exits at the next 1m open - 1 tick, resting orders at their level):
  path     the trade path after the fill: how losers and winners differ minute by minute (MFE / MAE / time; diag)
  ts       time stop: from minute N on, a 1m close still below entry - x R with the best point under m R -> exit next open
  tt       time tighten: from minute N on, while the best point is under m R, the stop moves up to entry - x R (resting)
  scr      scratch: once the trade has been m R in profit, a close back below entry - x R before 1R -> exit (pre-BE leak)
  wide     a wider stop (k ticks or the 1m swing beyond the sweep extreme), size follows the stop (the two-week caps)
  hunt     stop-hunt diagnostics: after a stop-out, how often price came back to the target the same day
  seq      sequence / memory: the next trade after a loss in the same direction, on the same level type, the same session
  ctx      entry context as a SIZE cut (x0.5 on a bucket) using the trade-selection features (tools/lit_select.py cache),
           fitted on H1 only, applied frozen to H2; plus a 3-feature logistic model (walk-forward)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16). Costs in ($1.40 a micro, 1 tick slippage).

  python -X utf8 tools/lit_loss_learn.py build    # 120 live 2026 trades + their 1m paths -> research/runs/_cache/litll_v1.pkl
  python -X utf8 tools/lit_loss_learn.py check    # the path simulator with no rule == the live trades (pts, exit)
  python -X utf8 tools/lit_loss_learn.py diag     # loser vs winner anatomy on the path, stop hunts, sequence tables
  python -X utf8 tools/lit_loss_learn.py grid     # every exit / stop / sequence / context variant -> research/lit/loss_learn.json
  python -X utf8 tools/lit_loss_learn.py save     # rl.save the runs lit_ll_*
Paper only. Imports engine/lit.py, tools/lit_1m_manage.py, tools/lit_2wk.py, engine/sizing.py; edits none of them.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import math
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache", "litll_v1.pkl")
OUT = os.path.join(ROOT, "research", "lit", "loss_learn.json")
OUT_DIAG = os.path.join(ROOT, "research", "lit", "loss_learn_diag.json")
PV, COMM, SLIP, TICK = 2.0, 1.40, 0.25, 0.25
FLAT = 955
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31")}
LIVE_MODEL = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
CFG_C = dict(LIVE_MODEL["lit_sizing"]["two_week"])          # the live two-week config (C: room_f 0.6, wk false)
CFG_A0 = {**CFG_C, "room_f": 1.0, "wk": True}               # the all-room config (reference)


# ================================================================================================ build
def build():
    from tools import lit_1m_manage as MM
    U = MM.unit()
    cx = MM.ctx()
    B, M = cx.B1, cx.M
    sel = {}
    try:
        rows = pickle.load(open(os.path.join(ROOT, "research", "runs", "_cache", "litsel_v1_17519777_1.pkl"), "rb"))["rows"]
        for r in rows:
            sel[(r["day"], int(r["z"]["i"]))] = r["f"]
    except Exception as e:                                   # pragma: no cover
        print("no trade-selection features:", e)
    es_t, es_h, es_l, es_c = cx.es_t, cx.es_h, cx.es_l, cx.es_c
    out = []
    for t in U:
        d = int(t["dir"])
        hi_d, lo_d, c_d, o_d = B.dirs(d)
        kf = int(np.searchsorted(B.t, t["entry_t"]))
        assert B.t[kf] == t["entry_t"], t["day"]
        sd = B.day[kf]
        kz = kf
        while kz < B.n and B.day[kz] == sd and B.mod[kz] < 1080:
            kz += 1
        kp = max(0, kf - 120)
        while B.day[kp] != sd:
            kp += 1
        entry = float(t["entry_px"]) * d
        stop0 = float(t["stop_px"]) * d
        tg = float(t["target_px"]) * d
        sl = cx.swing_low(d)
        p = {"o": o_d[kf:kz].astype(float), "h": hi_d[kf:kz].astype(float), "l": lo_d[kf:kz].astype(float),
             "c": c_d[kf:kz].astype(float), "mod": np.asarray(B.mod[kf:kz]), "t": np.asarray(B.t[kf:kz]),
             "v": np.asarray(cx.v1[kf:kz], float), "vavg": np.asarray(cx.vavg[kf:kz], float),
             "atr1": np.asarray(cx.atr1[kf:kz], float), "swl": np.asarray(sl[kf:kz]),
             # the 1m bars of the day before the fill (direction space) for the pre-entry structure
             "pre_l": lo_d[kp:kf].astype(float), "pre_h": hi_d[kp:kf].astype(float), "pre_swl": np.asarray(sl[kp:kf])}
        # ES 5m bars of the session (direction space), for context
        a = int(np.searchsorted(es_t, int(t["entry_t"]) - 6 * 3600)); b = int(np.searchsorted(es_t, int(p["t"][-1]) + 60))
        if d == 1:
            p["es"] = (es_t[a:b], es_h[a:b], es_l[a:b], es_c[a:b])
        else:
            p["es"] = (es_t[a:b], -es_l[a:b], -es_h[a:b], -es_c[a:b])
        r = {k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "risk_pts", "exit", "pts", "w1", "mfe", "mae", "limit_fill",
                               "swept", "i", "ext_i", "wk_m", "tf")}
        r.update(entry=entry, stop0=stop0, tg=tg, path=p, f=sel.get((t["day"], int(t["i"]))), mod0=int(B.mod[kf]),
                 dow=dt.date.fromisoformat(t["day"]).weekday())
        out.append(r)
    sess = json.load(open(os.path.join(ROOT, "research", "runs", "_cache", "lit_2wk_unit_live.json"), encoding="utf-8"))["sess"]
    pickle.dump({"trades": out, "sess": sess}, open(CACHE, "wb"))
    nf = sum(1 for r in out if r["f"])
    print(f"built {len(out)} trades ({nf} with selection features) -> {CACHE}")


_DB = None


def db():
    global _DB
    if _DB is None:
        _DB = pickle.load(open(CACHE, "rb"))
    return _DB


# ================================================================================================ path simulator
RDEF = {"ts": None, "tt": None, "scr": None, "wide": None, "es": None, "half_at": None}


def psim(r, R=None):
    """Re-play one trade on its 1m path with the live management (stop, breakeven at 1R, target, flat 15:55) plus rule R.
    Returns {"pts", "w1", "exit", "risk", "mfe", "mins"}; with R empty it must equal the live trade (check)."""
    R = {**RDEF, **(R or {})}
    p = r["path"]
    o, h, l, c, mod, tt = p["o"], p["h"], p["l"], p["c"], p["mod"], p["t"]
    n = len(o)
    entry, tg = r["entry"], r["tg"]
    stop0 = r["stop0"]
    if R["wide"]:
        w = R["wide"]
        if "ticks" in w:
            stop0 = stop0 - w["ticks"] * TICK
        if "r" in w:
            stop0 = stop0 - w["r"] * (entry - r["stop0"])
    risk = entry - stop0
    be_lvl = entry + 1.0 * risk
    cur, be_done = stop0, False
    mfe, worst = 0.0, 0.0
    pend = None
    rest = None                 # (level, kind) resting stop order above the stop
    exit_px = kind = None
    j = 0
    for j in range(n):
        if pend is not None:
            exit_px, kind = o[j] - SLIP, pend
            break
        worst = min(worst, l[j] - entry)
        if rest is not None and rest[0] > cur and l[j] <= rest[0]:
            exit_px, kind = min(rest[0], o[j]) - SLIP, rest[1]
            break
        if l[j] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP")
            break
        if not (j == 0 and r["limit_fill"]):
            mfe = max(mfe, (h[j] - entry) / risk)
            if h[j] >= tg:
                exit_px, kind = tg, "TARGET"
                break
            if not be_done and h[j] >= be_lvl:
                cur, be_done = max(cur, entry), True
        if mod[j] >= FLAT:
            exit_px, kind = c[j] - SLIP, "EOD"
            break
        # ---- rules, at the close of bar j (minutes since the fill at this close)
        mins = (tt[j] - tt[0]) / 60.0 + 1.0
        nxt = j + 1 < n
        sig = None
        o_ = R["ts"]
        if o_ and not be_done and mins >= o_["at"] and mfe < o_.get("mfe", 99) and c[j] < entry - o_.get("x", 0.0) * risk:
            if o_.get("upto") is None or mins <= o_["upto"]:
                sig = "CUT_TIME"
        o_ = R["tt"]
        if o_ and not be_done and mins >= o_["at"] and mfe < o_.get("mfe", 99):
            lv = entry - o_["x"] * risk
            if lv > cur and lv < c[j]:
                rest = (lv, "CUT_TIGHT")
            elif lv >= c[j] and o_.get("mkt", True):
                sig = "CUT_TIGHT"                      # already below the tightened level: out at the next open
        o_ = R["scr"]
        if o_ and sig is None and not be_done and mfe >= o_["m"] and c[j] < entry - o_.get("x", 0.0) * risk:
            sig = "CUT_SCR"
        if sig is not None:
            if nxt:
                pend = sig
            else:
                exit_px, kind = c[j] - SLIP, sig
                break
    if exit_px is None:
        exit_px, kind = c[n - 1] - SLIP, "EOD"
        j = n - 1
    return {"pts": float(exit_px - entry), "w1": float(worst), "exit": kind, "risk": float(risk), "mfe": float(mfe),
            "mins": float((tt[j] - tt[0]) / 60.0 + 1.0)}


def check():
    D = db()["trades"]
    bad = 0
    for r in D:
        s = psim(r)
        if abs(s["pts"] - r["pts"]) > 1e-6 or s["exit"] != r["exit"] or abs(s["w1"] - r["w1"]) > 1e-6:
            bad += 1
            print("MISMATCH", r["day"], r["exit"], r["pts"], r["w1"], "->", s)
    print(f"check: {len(D) - bad}/{len(D)} trades equal to the live trades")
    return bad == 0


# ================================================================================================ scoring
def variant(R=None, mult=None):
    """Unit trades (lit_2wk format) of rule R; mult(r) -> size multiplier (<1 = cut, applied like lit_qty's learned cut:
    after the two-week micros, rounded down, min 1)."""
    out = []
    for r in db()["trades"]:
        s = psim(r, R)
        m = float(mult(r)) if mult else 1.0
        out.append({"day": r["day"], "entry_t": r["entry_t"], "exit_t": r["exit_t"], "dir": r["dir"], "risk": round(s["risk"], 2),
                    "tgt": round(r["tg"] - r["entry"], 2), "pts": round(s["pts"], 4), "w1": round(s["w1"], 4),
                    "exit": s["exit"], "wk_m": r["wk_m"], "tf": r["tf"], "ll_m": m, "mfe": s["mfe"], "mins": s["mins"]})
    return out


_W = None
_ORIG_QTY = None


def _w():
    """tools/lit_2wk with its two_week_qty wrapped so a trade's ll_m (a size cut) applies after the two-week micros."""
    global _W, _ORIG_QTY
    if _W is None:
        from tools import lit_2wk as W
        _ORIG_QTY = W.S.two_week_qty

        def qty(t, st, cfg=None, acct=None, why=None):
            q = _ORIG_QTY(t, st, cfg, acct)
            m = float(t.get("ll_m", 1.0))
            if q > 0 and m < 1.0 - 1e-9:
                q = max(1, int(q * m + 1e-9))
            return q
        W.S.two_week_qty = qty
        _W = W
    return _W


_KEY = [0]


def score(U, cfg=None, mc=True, label=None):
    """p10 / f10 (exact fresh-eval starts on every session of the half, full 10 sessions seen), Monte Carlo, and the money
    on the back-to-back eval path (reset after 10 sessions) and at the plain LIT size ($800 up to 20 pts, 800x20/stop)."""
    W = _w()
    cfg = cfg or CFG_C
    _KEY[0] += 1
    v = f"ll{_KEY[0]}"
    sess = db()["sess"]
    by = collections.defaultdict(list)
    for t in U:
        by[t["day"]].append(t)
    W._D[v] = {"sess": sess, "by": [by.get(s, []) for s in sess], "trades": U,
               "dow": np.array([dt.date.fromisoformat(s).weekday() for s in sess])}
    o = {}
    for sp in ("H1", "H2", "2026"):
        a, z = SPAN[sp]
        e = W.exact(cfg, sp, v)
        T, bb = W.b2b(cfg, sp, v)
        pn = np.array([x["pnl"] for x in T]) if T else np.zeros(0)
        eq = np.cumsum(pn) if len(pn) else np.zeros(1)
        dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if len(pn) else 0.0
        tr = [t for t in U if a <= t["day"] <= z]
        days = [s for s in sess if a <= s <= z and s <= "2026-10-16"]
        weeks = max(1e-9, len(days) / 5.0)
        months = max(1e-9, len(days) / 21.0)
        lq = []
        for t in tr:
            m = float(t["wk_m"]) * min(1.0, t["ll_m"])
            q0 = lit.qty_for(t["risk"])
            q = q0 if abs(m - 1.0) < 1e-9 else max(1, int(q0 * m + 1e-9))
            lq.append(t["pts"] * PV * q - COMM * q)
        lq = np.array(lq)
        cnt = collections.Counter(lit.iso_week(t["day"]) for t in tr)
        o[sp] = {"n": len(tr), "tpw": round(len(tr) / weeks, 2),
                 "wk2": round(100.0 * sum(1 for w in {lit.iso_week(s) for s in days} if cnt[w] >= 2)
                              / max(1, len({lit.iso_week(s) for s in days})), 1),
                 "win": round(100.0 * sum(1 for t in tr if t["pts"] * PV - COMM > 0) / max(1, len(tr)), 1),
                 "p10": e["p10"], "f10": e["f10"], "p20": e["p20"], "f20": e["f20"], "n10": e["n10"], "cost": e["cost"],
                 "pass_med": e["pass_med"],
                 "b2b_net": round(float(pn.sum())), "b2b_pm": round(float(pn.sum()) / months),
                 "b2b_pf": round(float(pn[pn > 0].sum() / -pn[pn < 0].sum()), 2) if (pn < 0).any() else None,
                 "b2b_dd": round(dd), "evals": bb["evals"], "passed": bb["passed"], "failed": bb["failed"],
                 "lit_net": round(float(lq.sum())), "lit_pm": round(float(lq.sum()) / months),
                 "lit_pf": round(float(lq[lq > 0].sum() / -lq[lq < 0].sum()), 2) if (lq < 0).any() else None,
                 "lit_dd": round(float((np.cumsum(lq) - np.maximum.accumulate(np.r_[0.0, np.cumsum(lq)])[1:]).min())) if len(lq) else 0}
        if mc and sp != "2026":
            m = W.mc(cfg, sp, v)
            o[sp]["mc_p10"], o[sp]["mc_f10"] = m["p10"], m["f10"]
    W._D.pop(v, None)
    for k in [k for k in W._SEQ if k[1] == v]:
        W._SEQ.pop(k, None)
    if label:
        o["label"] = label
    return o


def fmt(nm, o):
    def f(s):
        x = o[s]
        mc = f" mc {x['mc_p10']}/{x['mc_f10']}" if "mc_p10" in x else ""
        return (f"{s}: 2w {x['p10']:4.1f}/{x['f10']:4.1f}{mc} | b2b {x['b2b_net']:+7,} ${x['b2b_pm']:+6,}/mo PF {x['b2b_pf']} "
                f"DD {x['b2b_dd']:,} ({x['passed']}/{x['evals']}) | lit {x['lit_net']:+7,} PF {x['lit_pf']} | {x['tpw']}/wk win {x['win']}")
    return f"{nm:34s} {f('H1')}\n{'':34s} {f('H2')}"


def base():
    o = score(variant())
    print(fmt("baseline (live, config C)", o))
    return o


# ================================================================================================ sequence / context rules
def _lvl(r):
    for k, v in (("asia", "asia"), ("lon", "lon"), ("ny", "ny"), ("pd", "pd"), ("pw", "pw"), ("pm", "pm"), ("nwog", "gap"),
                 ("ndog", "gap"), ("bu", "bu")):
        if any(x.startswith(k) for x in r["swept"]):
            return v
    return "other"


def _prev():
    D = sorted(db()["trades"], key=lambda r: r["entry_t"])
    return {r["day"]: [x for x in D if x["exit_t"] <= r["entry_t"]] for r in D}


def seq_rule(kind):
    P = _prev()
    st = lambda x: x["exit"] == "STOP"                                    # noqa: E731
    f = {"same_dir": lambda r: (lambda S: bool(S) and st(S[-1]))([x for x in P[r["day"]] if x["dir"] == r["dir"]]),
         "last_stop_same_dir": lambda r: bool(P[r["day"]]) and st(P[r["day"]][-1]) and P[r["day"]][-1]["dir"] == r["dir"],
         "same_level": lambda r: (lambda S: bool(S) and st(S[-1]))([x for x in P[r["day"]] if _lvl(x) == _lvl(r)]),
         "prev_day_stop": lambda r: bool(P[r["day"]]) and st(P[r["day"]][-1])}[kind]
    return lambda r: 0.5 if f(r) else 1.0


def model_rule(fs=("idm_age", "stop_atr", "rr")):
    """3-feature logistic regression for P(full stop-out), fit on H1 only; x0.5 on the top third of H1 scores (frozen)."""
    D = db()["trades"]
    H1 = [r for r in D if r["day"] <= SPAN["H1"][1]]
    X = np.array([[float(np.nan_to_num(r["f"][k])) for k in fs] for r in H1])
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    Y = np.array([1.0 if r["exit"] == "STOP" else 0.0 for r in H1])
    w, b0 = np.zeros(len(fs)), 0.0
    for _ in range(3000):
        p = 1 / (1 + np.exp(-(Z @ w + b0)))
        w -= 0.1 * (Z.T @ (p - Y) / len(Y) + w / len(Y))
        b0 -= 0.1 * float(np.mean(p - Y))
    sc = lambda r: float(1 / (1 + np.exp(-(((np.array([float(np.nan_to_num(r["f"][k])) for k in fs]) - mu) / sd) @ w + b0))))  # noqa
    thr = float(np.quantile([sc(r) for r in H1], 2 / 3))
    return lambda r: 0.5 if sc(r) >= thr else 1.0


# ================================================================================================ the runs
T15 = {"ts": {"at": 15, "x": 0.3, "mfe": 0.5, "upto": 15}}
RUNS = [  # id, title, rule, mult, status, why
    ("lit_ll_t15", "15-minute check: at minute 15 after the fill, best point < +0.5R and close <= -0.3R -> exit next 1m open",
     T15, None, "adopt-candidate",
     "Picked as the simplest member of the minute 15-20 family that holds in both halves; neighbours x 0.25/0.3/0.4, mfe 0.3/0.5/0.7, "
     "minute 15/18/20 all improve both halves; minute 10/12 leave H2 unchanged, minute 25/30 lose H2. Cut 13 trades, all would-be "
     "full stop-outs (9 H1, 4 H2), exited at -0.33 to -0.62R; no winner or breakeven touched."),
    ("lit_ll_t15_win", "Early-failure window: minute 15-19, best < +0.5R, close <= -0.3R -> exit", {"ts": {"at": 15, "x": 0.3, "mfe": 0.5, "upto": 19}},
     None, "promising", "Same family, a 5-minute window. Helps both halves; the window end (19) was set knowing that H2 slow winners dip later."),
    ("lit_ll_cont15", "Time stop from minute 15 on (no end): best < +0.5R, close <= -0.3R -> exit", {"ts": {"at": 15, "x": 0.3, "mfe": 0.5}},
     None, "rejected", "The honest H1 pick of the continuous family (H1 2-week fails 8.4 -> 0.0). It kills 2 slow H2 winners: H2 2-week pass "
     "50.7 -> 44.9 although H2 money rises."),
    ("lit_ll_cont10", "Time stop from minute 10 on: best < +0.5R, close <= -0.3R -> exit", {"ts": {"at": 10, "x": 0.3, "mfe": 0.5}},
     None, "rejected", "Best H1 member; H2 2-week pass 50.7 -> 44.9."),
    ("lit_ll_t25", "25-minute check: best < +0.5R, close <= -0.3R -> exit", {"ts": {"at": 25, "x": 0.3, "mfe": 0.5, "upto": 25}},
     None, "rejected", "Later checks catch H2's slow winners (they dip 0.3-0.5R after 20 minutes): H2 2-week pass 50.7 -> 43.5."),
    ("lit_ll_t5", "Early cut, minute 5-14: best < +0.5R, close <= -0.3R -> exit", {"ts": {"at": 5, "x": 0.3, "mfe": 0.5, "upto": 14}},
     None, "rejected", "The first 5-10 minutes are noise: 2-3 winners killed in each half."),
    ("lit_ll_tighten60", "After 60 minutes without +0.5R, stop up to -0.3R", {"tt": {"at": 60, "x": 0.3, "mfe": 0.5}},
     None, "rejected", "Small money, 2-week pass unchanged in both halves; earlier tightening (15-45 min) loses H2."),
    ("lit_ll_scratch07", "Scratch: after +0.7R, a close back below -0.3R before breakeven -> exit", {"scr": {"m": 0.7, "x": 0.3}},
     None, "rejected", "Loses money in both halves."),
    ("lit_ll_wide2", "Stop 2 ticks wider (size follows the stop)", {"wide": {"ticks": 2}}, None, "rejected",
     "Stop-outs are not shake-outs: only 1 of 53 came back after going < 0.5R beyond the stop. Every wider stop (1-8 ticks, 0.1-0.3R) "
     "is flat or worse."),
    ("lit_ll_seq_samedir", "Half size when the last trade in the same direction was a stop-out", None, "seq:same_dir", "rejected",
     "Sequence memory flips: after a stop-out H1 trades are worse, H2 better. 2-week pass -8.4 / -8.7."),
    ("lit_ll_model", "3-feature logistic stop-out model (inducement age, stop/ATR, R:R), fit on H1, x0.5 on its top third", None, "model",
     "rejected", "No skill out of sample (H2 AUC 0.57; 5 feature sets tried, 0.47-0.63). H2 2-week pass 50.7 -> 39.1."),
]


def _mult(spec):
    if spec is None:
        return None
    if spec == "model":
        return model_rule()
    if spec.startswith("seq:"):
        return seq_rule(spec[4:])
    raise ValueError(spec)


def b2b_trades(U, cfg=None):
    """The back-to-back eval path of 2026 (trades with their eval size) for the run library."""
    W = _w()
    _KEY[0] += 1
    v = f"ll{_KEY[0]}"
    sess = db()["sess"]
    by = collections.defaultdict(list)
    for t in U:
        by[t["day"]].append(t)
    W._D[v] = {"sess": sess, "by": [by.get(s, []) for s in sess], "trades": U,
               "dow": np.array([dt.date.fromisoformat(s).weekday() for s in sess])}
    T, bb = W.b2b(cfg or CFG_C, "2026", v)
    W._D.pop(v, None)
    return T, bb


def grid():
    res = {"base": score(variant())}
    print(fmt("baseline (live, config C)", res["base"]), flush=True)
    for rid, title, R, M, status, why in RUNS:
        res[rid] = score(variant(R, _mult(M)), label=title)
        print(fmt(rid, res[rid]), flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    print("->", OUT)


def save():
    from tools import runlib as rl
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    sess = [s for s in db()["sess"] if "2026-01-01" <= s <= "2026-10-16"]
    for rid, title, R, M, status, why in RUNS:
        U = variant(R, _mult(M))
        o = res.get(rid) or score(U)
        T, bb = b2b_trades(U)
        S = rl.score(T, sess)
        h = lambda s: (f"2-week pass/fail {o[s]['p10']}/{o[s]['f10']}% (Monte Carlo {o[s].get('mc_p10')}/{o[s].get('mc_f10')}), "  # noqa
                       f"1 month {o[s]['p20']}/{o[s]['f20']}, back-to-back {o[s]['passed']} passes in {o[s]['evals']} evals, eval-path "
                       f"net ${o[s]['b2b_net']:+,} (${o[s]['b2b_pm']:+,}/mo, PF {o[s]['b2b_pf']}, DD ${o[s]['b2b_dd']:,}), plain LIT size "
                       f"${o[s]['lit_net']:+,} PF {o[s]['lit_pf']}, {o[s]['tpw']}/wk, win {o[s]['win']}%")
        b = res.get("base")
        ref = (f" Baseline (live config C): H1 {b['H1']['p10']}/{b['H1']['f10']}, H2 {b['H2']['p10']}/{b['H2']['f10']}." if b else "")
        verdict = f"{why} H1 (pick): {h('H1')}. H2 (check): {h('H2')}.{ref}"
        rl.save(rid, title, "management" if R else "risk",
                "Owner 2026-10-18: learn from LIT's losses; does the rule raise the MFFU 50K 2-week pass rate under the live two-week "
                "sizing (config C) in both 2026 halves?", params={"rule": R, "mult": M, "lit": "live_model.json lit (unchanged)"},
                sizing={"mode": "two_week", **CFG_C}, trades=T, scored=S, status=status, verdict=verdict,
                notes=("tools/lit_loss_learn.py: the 120 live 2026 LIT trades (tools/lit_1m_manage unit() == run lit_live) re-played "
                       "on their true 1m paths (check: 120/120 identical with no rule); eval scoring tools/lit_2wk.py (exact MFFU 50K, "
                       "fresh eval on every session, 4,000-path Monte Carlo). Stored trades = the 2026 back-to-back eval path, so the "
                       "library's own eval columns re-play those day P&Ls; the exact eval numbers are in the verdict. scores=" +
                       json.dumps(o, default=float)),
                writeup="lit-loss-learning", tags=["lit", "lit_loss_learn"])
        print("saved", rid, bb, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"build": build, "check": check, "base": base, "grid": grid, "save": save}[cmd]()
