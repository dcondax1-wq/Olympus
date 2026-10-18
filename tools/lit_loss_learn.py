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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"build": build, "check": check}[cmd]()
