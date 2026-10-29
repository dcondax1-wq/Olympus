"""ATLAS v2 PAPER SHADOW (owner 2026-10-25, research/writeups/atlas-v2.md candidate 1b). Paper only: never routed.

What it is: the 25K eval path of candidate 1b run live on the same bars as the live ATLAS, next to it:
  members   EMA + MACD + S/R (today's ATLAS) + the two stop hunts sh_asia and sh_trend at HALF size ("weights" 0.5)
  eval      MFFU Builder 25K rules (target $1,500, $1,000 EOD trailing max loss locked at start + $100, $600 soft daily
            loss, 20 micros), need size (engine/account_b.qty, LIT's two_week "one winner passes" on the 25K preset), one
            position, max 2 trades a day, never opposite to LIT (open trade, armed setup; LIT entering the other way closes
            it: HEDGE), stuck = room under $200 ("min_room": 200) -> buy a new eval ($63) from the next session.
  = tools/atlas_v2.py score() (executor tools/atlas.py + tools/second_account_b.py) on the live members' trades;
  tests/test_atlas_v2_shadow.py replays 2026 and gets the research path (run atlas_v2_hunts_w05_stuck200).

Where it runs:
  cloud     tools/cloud_monitor.py: the members' frozen paper ledgers (state "second") + the LIT run of the same bars ->
            state key "atlas_v2" (its own frozen paper ledger + eval tracker); pushes of kind "second" titled
            "ATLAS v2 PAPER ...", only when second_model.json "atlas_v2": {"push": true} (default false = recorded, not sent;
            the app's per-kind level for "second" applies on top).
  PC        engine/live.py LiveBot._second_tick (the paper job of engine/bg_worker.py, a thread when the worker is off;
            after LIT's routing): the same step on the PC's own second run -> data/live_state_atlas_v2.json (gitignored),
            heartbeat "second": {"atlas_v2": compact}.
Nothing here imports a broker / adapter / NinjaTrader or writes an order file (tests/test_atlas_v2_shadow.py checks it);
second_model.json "account_b" and the live ATLAS are untouched: switching the real ATLAS to v2 later is the one JSON change
in research/writeups/atlas-v2.md ("weights" + "min_room", engine/account_b.py supports both, off when absent).

Frozen ledger: a decision (taken with its micros / skipped with the reason) is made once, on the bars and the eval state
known at that poll, and never revised; a taken trade is booked when its member's paper trade has finished (or LIT entered
the other way: HEDGE, cut at that bar's open + 1 tick). Later candidates wait while a taken trade is still open (one
position). Sessions = trading days the shadow saw bars for; a session is closed (eval checks) once the next trading day
starts. Live approximations (documented, not in the research): LIT's armed windows come from each LIT signal until its
fill / the 30-minute limit expiry / the pending setup's expiry as the polls saw them.

Scorecard (build(): research/second/atlas_v2_scorecard.json from the research run's path trades, bootstrap like
engine/second_scorecard): "hunts" = the sh_asia + sh_trend trades the shadow took (cum R at their real size vs the 2026 H2
band; ready after 20+), "account" = every shadow trade ($ vs the band). The owner decides after 20+ hunt trades.

    python -X utf8 -m engine.atlas_v2 build     # the bands (~2 s)
    python -X utf8 -m engine.atlas_v2 show      # the card on data/cloud_state.json (if any)
"""
from __future__ import annotations

import bisect
import datetime as _dt
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAND_PATH = os.path.join(ROOT, "research", "second", "atlas_v2_scorecard.json")
RUN = "atlas_v2_hunts_w05_stuck200"
VERSION = 1
LABEL = "ATLAS v2 (paper shadow)"
SRC = {"ema_lon_vix": "EMA", "macd_sweep": "MD", "sr_nyreclaim": "SR", "sh_asia": "SHA", "sh_trend": "SHT"}
KEY_OF = {v: k for k, v in SRC.items()}
SHORT = {"EMA": "EMA", "MD": "MACD", "SR": "S/R", "SHA": "Asia hunt", "SHT": "Trend hunt"}
HUNTS = ("SHA", "SHT")
# candidate 1b (research/writeups/atlas-v2.md "Exact JSON"): the account_b block it would be, kept here, never written
SPEC = {"plan": "builder25k", "sizing": "need", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim", "sh_asia", "sh_trend"],
        "weights": {"sh_asia": 0.5, "sh_trend": 0.5}, "min_room": 200.0}
PRICE = 63.0
MAX_DAY = 2
PV, SLIP = 2.0, 0.25
WAIT_S = 30 * 60                 # LIT's 5m CISD limit works 30 minutes (live_model.json lit "wait" 6 bars)
INF = 1 << 62
# the research numbers of candidate 1b (eval money less the $63 fees, mean of back-to-back paths started every 5th session;
# 2-week pass / fail; research/writeups/atlas-v2.md), shown next to the paper result
RESEARCH = {"H1": {"label": "2026 H1 (pick)", "usd": 10876, "per_month": 1813, "p10": 67.2, "f10": 0.0, "tpw": 4.8},
            "H2": {"label": "2026 H2 (check)", "usd": 3859, "per_month": 1103, "p10": 55.1, "f10": 0.0, "tpw": 4.8},
            "2025": {"label": "2025", "usd": 240, "per_month": 20, "p10": 26.5, "f10": 0.0},
            "2021-24": {"label": "2021-24", "usd": 4575, "per_month": 120, "p10": 24.3, "f10": 0.0}}
TODAY = {"H1": 8500, "H2": 2029, "2025": -1935, "2021-24": -1429}


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def trading_day(ts) -> str:
    from .account_b import trading_day as td
    return td(ts)


# ---------------------------------------------------------------------------------------------------------------- spec
_SPEC = {}


def spec(eval_start: str | None = None) -> dict:
    """The account_b spec of candidate 1b (engine/account_b.normalize, Builder 25K, weights + min_room). Never routed."""
    k = eval_start or ""
    if k not in _SPEC:
        from . import account_b as AB
        _SPEC[k] = AB.normalize({"account": "ATLAS-v2-paper-shadow", "plan": SPEC["plan"], "eval_start": eval_start or "",
                                 "sizing": SPEC["sizing"], "strategies": list(SPEC["strategies"]), "weights": dict(SPEC["weights"]),
                                 "min_room": SPEC["min_room"]}, lit_account=None)
    return _SPEC[k]


def rules() -> dict:
    return spec()["rules"]


def cfg(path: str | None = None) -> dict:
    """second_model.json "atlas_v2" (display / push switches only; the candidate itself is SPEC). Never raises."""
    from . import second
    try:
        with open(path or second.CFG_PATH, encoding="utf-8") as fh:
            c = json.load(fh).get("atlas_v2")
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def push_on(c: dict | None = None) -> bool:
    c = cfg() if c is None else c
    return c.get("push") is True


def enabled(c: dict | None = None) -> bool:
    c = cfg() if c is None else c
    return c.get("on", True) is not False


# ---------------------------------------------------------------------------------------------------------------- bars
class Bars:
    """t / o / h / l arrays of a bar frame (time, open, high, low) or of research bars (engine/lit.XBars)."""

    def __init__(self, src, secs):
        if src is None:
            self.t = np.zeros(0, np.int64)
            self.o = self.h = self.l = np.zeros(0)
        elif hasattr(src, "t") and hasattr(src, "o"):
            self.t, self.o, self.h, self.l = np.asarray(src.t, np.int64), np.asarray(src.o, float), np.asarray(src.h, float), np.asarray(src.l, float)
        else:
            d = src.sort_values("time")
            self.t = d["time"].astype(np.int64).values
            self.o, self.h, self.l = d["open"].astype(float).values, d["high"].astype(float).values, d["low"].astype(float).values
        self.secs = int(secs)


def _pick(bars1: Bars | None, bars5: Bars | None, entry_t: int) -> Bars | None:
    """Research rule (tools/second_mix.second_units): the 1m bars once they cover the day before the entry, else 5m."""
    if bars1 is not None and len(bars1.t) and int(entry_t) >= int(bars1.t[0]) + 86400:
        return bars1
    return bars5 if bars5 is not None and len(bars5.t) else bars1


def path_of(u: dict, B: Bars | None, upto: int | None = None) -> dict:
    """The unit's open-path fields (pt bar open times after the entry bar, po open pts in the trade's direction, pw worst
    pts before that bar) and, for a finished unit, w1 (worst open pts, = tools/second_mix.second_units)."""
    dr, e, risk = int(u["dir"]), float(u["entry"]), float(u["risk"])
    if B is None or not len(B.t):
        return {"pt": np.zeros(0, np.int64), "po": np.zeros(0), "pw": np.zeros(0), "w1": min(0.0, float(u.get("pts") or 0.0))}
    k0 = int(np.searchsorted(B.t, int(u["entry_t"]), side="right"))
    end = int(u["exit_t"]) if u.get("exit_t") else int(upto if upto is not None else B.t[-1] + B.secs)
    kx = int(np.searchsorted(B.t, end - B.secs))
    lo = B.l if dr == 1 else -B.h
    out = {}
    if u.get("exit_t"):
        pts = float(u["pts"])
        w = float(lo[k0:kx].min()) - e * dr if kx > k0 else 0.0
        out["w1"] = round(max(-(risk + 0.25), min(0.0, w, pts)), 4)
    else:
        kx = min(kx, len(B.t) - 1)
    op = (B.o[k0:kx + 1] * dr - e * dr) if kx >= k0 else np.zeros(0)
    lw = np.minimum.accumulate(np.r_[0.0, lo[k0:kx] - e * dr]) if kx >= k0 else np.zeros(0)
    out.update(pt=B.t[k0:kx + 1].astype(np.int64), po=np.round(op, 2), pw=np.maximum(np.round(lw, 2), -(risk + 0.25)))
    return out


def unit_of(row: dict, key: str, bars1: Bars | None = None, bars5: Bars | None = None) -> dict | None:
    """A member's paper trade (engine/second.run trade / ledger row) -> an account-B unit (tools/second_mix.second_units /
    tools/atlas_v2._sh_units): risk, tgt (no target: 2R hunts / 3R others), and once finished pts per micro + w1 + path."""
    src = SRC.get(key)
    try:
        dr = 1 if int(row["dir"]) > 0 else -1
        e, s = float(row["entry"]), float(row["stop"])
    except (KeyError, TypeError, ValueError):
        return None
    risk = abs(e - s)
    if src is None or risk <= 0 or row.get("entry_t") is None:
        return None
    tg = _num(row.get("target"))
    tgt = abs(tg - e) if tg is not None else (2.0 if src in HUNTS else 3.0) * risk
    fin = row.get("exit_kind") not in (None, "", "OPEN") and _num(row.get("exit")) is not None and row.get("exit_t")
    u = {"id": f"{src}:{int(row['entry_t'])}", "key": key, "src": src, "day": row.get("day") or trading_day(int(row["entry_t"])),
         "entry_t": int(row["entry_t"]), "dir": dr, "entry": e, "stop": s, "target": tg, "risk": round(risk, 4), "tgt": round(tgt, 4),
         "open": not fin}
    if fin:
        u.update(exit_t=int(row["exit_t"]), exit=str(row["exit_kind"]), pts=round((float(row["exit"]) - e) * dr, 4))
    B = _pick(bars1, bars5, u["entry_t"])
    u["_B"] = B
    if fin:
        u.update(path_of(u, B))
    return u


def cut_at(u: dict, ts: int, B: Bars | None = None):
    """(pts per micro incl. 1 tick slippage, worst pts) of a unit flattened at ts (LIT entered the other way;
    = tools/second_mix.cut_at). An open unit gets its path from the bars first."""
    if "pt" not in u or u.get("open"):
        u = {**u, **path_of(u, B if B is not None else u.get("_B"), upto=int(ts) + 60)}
    k = int(np.searchsorted(u["pt"], ts))
    if k >= len(u["pt"]):
        return (u["pts"], u["w1"]) if not u.get("open") else (None, None)
    pts = min(float(u["po"][k]), 1e9) - SLIP
    w = min(0.0, float(u["pw"][k]), pts)
    return pts, w


# ---------------------------------------------------------------------------------------------------------------- LIT
def lit_inputs(res: dict | None, now: int, prev_armed=None) -> tuple:
    """(LIT trades [{"day", "entry_t", "exit_t" (None = open), "dir"}], armed windows [[day, dir, a, z]]) from a lit_live
    run (res: trades, state.position / enter_now / setups, signals). prev_armed = the windows seen by earlier polls (kept,
    a later poll only extends / closes them)."""
    T = []
    for t in (res or {}).get("trades") or []:
        if t.get("entry_t") is not None and t.get("dir") is not None:
            T.append({"day": t.get("day") or trading_day(int(t["entry_t"])), "entry_t": int(t["entry_t"]),
                      "exit_t": int(t["exit_t"]) if t.get("exit_t") else None, "dir": 1 if int(t["dir"]) > 0 else -1})
    st = (res or {}).get("state") or {}
    for p in (st.get("position"), st.get("enter_now")):
        if p and p.get("entry_t") is not None and not any(x["entry_t"] == int(p["entry_t"]) for x in T):
            T.append({"day": trading_day(int(p["entry_t"])), "entry_t": int(p["entry_t"]), "exit_t": None, "dir": 1 if int(p.get("dir") or 1) > 0 else -1})
    T.sort(key=lambda x: x["entry_t"])
    W = {(int(a[1]), int(a[2])): list(a) for a in prev_armed or []}
    exp = {}
    for side, s in (st.get("setups") or {}).items():
        if isinstance(s, dict) and s.get("arm_t") is not None:
            exp[(1 if side == "long" else -1, int(s["arm_t"]))] = max(int(s.get("expires_t") or 0), int(now))
    for s in (res or {}).get("signals") or []:
        if s.get("t") is None or s.get("dir") is None:
            continue
        d, a = (1 if int(s["dir"]) > 0 else -1), int(s["t"])
        day = s.get("day") or trading_day(a)
        stt = s.get("status")
        if stt in ("pending", "entering") or (d, a) in exp:
            z = max(exp.get((d, a), 0), int(now))
        elif stt == "filled":
            z = next((x["entry_t"] for x in T if x["dir"] == d and x["entry_t"] >= a), a + WAIT_S)
        else:
            z = a + WAIT_S
        W[(d, a)] = [day, d, a, int(z)]               # a signal no longer in the run's window keeps its last window
    return T, sorted(W.values(), key=lambda x: x[2])[-120:]


# ---------------------------------------------------------------------------------------------------------------- eval state
def _new_eval(n: int) -> dict:
    R = rules()
    return {"n": n, "start": None, "bal": 0.0, "peak": 0.0, "floor": -float(R["mll"]), "sess": 0, "day": None, "cum": 0.0,
            "nd": 0, "busy": 0, "failed": False}


def new_state(now: int, first_run: int | None = None) -> dict:
    fr = int(first_run if first_run is not None else now)
    return {"v": VERSION, "paper": True, "never_routed": True, "label": LABEL, "run": RUN, "first_run": fr, "t": int(now),
            "start_day": trading_day(fr), "ev": _new_eval(1), "evals": [], "ledger": {}, "skipped": [], "seen": [], "armed": [],
            "last_day": None, "open": None, "events": []}


def _end_eval(S: dict, result: str):
    ev, R = S["ev"], rules()
    bal = float(ev["bal"]) + (float(ev["cum"]) if ev["failed"] else 0.0)
    S["evals"].append({"n": ev["n"], "start": ev["start"], "end": ev["day"], "sessions": ev["sess"], "result": result,
                       "profit": round(bal, 2), "room": round(max(0.0, bal - float(ev["floor"])), 2),
                       "usd": round(sum(float(r.get("usd") or 0) for r in S["ledger"].values() if r.get("eval") == ev["n"]), 2)})
    S["events"] = (S.get("events") or [])[-40:] + [{"t": int(S.get("t") or 0), "kind": "eval", "n": ev["n"], "result": result,
                                                    "day": ev["day"], "profit": round(bal, 2), "sessions": ev["sess"]}]
    S["ev"] = _new_eval(ev["n"] + 1)


def _close_session(S: dict):
    """End of the current session: tools/atlas_v2.run_eval (fail / trail / pass / stuck under min_room)."""
    ev, R = S["ev"], rules()
    if ev["day"] is None:
        return
    if ev["failed"]:
        _end_eval(S, "FAIL")
        return
    ev["bal"] = float(ev["bal"]) + float(ev["cum"])
    ev["cum"] = 0.0
    if ev["bal"] <= ev["floor"]:
        _end_eval(S, "FAIL")
        return
    ev["peak"] = max(float(ev["peak"]), ev["bal"])
    ev["floor"] = min(max(float(ev["floor"]), ev["peak"] - float(R["mll"])), float(R["lock"]))
    if ev["bal"] >= float(R["target"]):
        _end_eval(S, "PASS")
    elif ev["bal"] - ev["floor"] < float(spec()["min_room"]):
        _end_eval(S, "STUCK")
    else:
        ev["day"] = None


def _open_session(S: dict, day: str):
    ev = S["ev"]
    ev.update(day=day, sess=int(ev["sess"]) + 1, cum=0.0, nd=0, busy=0, failed=False)
    if ev["start"] is None:
        ev["start"] = day
    S["last_day"] = day


def _goto(S: dict, day: str, sessions: list):
    """Make `day` the current session: close the current one and count the sessions in between (no trades)."""
    if S["ev"]["day"] == day:
        return
    if S["ev"]["day"] is not None:
        _close_session(S)
    last = S.get("last_day")
    i = bisect.bisect_right(sessions, last) if last else bisect.bisect_left(sessions, S["start_day"])
    while i < len(sessions) and sessions[i] < day:
        _open_session(S, sessions[i])
        _close_session(S)
        i += 1
    _open_session(S, day)


def close_through(S: dict, today: str, sessions: list):
    """Close every session before `today` (complete) when no trade is open."""
    if S.get("open"):
        return
    if S["ev"]["day"] is not None and S["ev"]["day"] < today:
        _close_session(S)
    last = S.get("last_day")
    i = bisect.bisect_right(sessions, last) if last else bisect.bisect_left(sessions, S["start_day"])
    while i < len(sessions) and sessions[i] < today:
        _open_session(S, sessions[i])
        _close_session(S)
        i += 1


def _state_for_size(S: dict) -> dict:
    ev = S["ev"]
    return {"profit": float(ev["bal"]), "cum": float(ev["cum"]), "room": float(ev["bal"]) + float(ev["cum"]) - float(ev["floor"]),
            "session": int(ev["sess"]), "n_today": 0}


def _side(d) -> str:
    return "LONG" if int(d) > 0 else "SHORT"


def _hedge_why(u, lit, armed_by_day):
    for x in lit:
        if x["day"] == u["day"] and x["dir"] != u["dir"] and x["entry_t"] <= u["entry_t"] < (x["exit_t"] if x["exit_t"] is not None else INF):
            return f"no hedging: LIT in a {_side(x['dir'])} trade"
    for day, d, a, z in armed_by_day.get(u["day"], ()):
        if d != u["dir"] and a <= u["entry_t"] < z:
            return f"no hedging: LIT {_side(d)} setup armed"
    return None


def _skip(S, u, why):
    S["skipped"] = (S.get("skipped") or [])[-79:] + [{"id": u["id"], "src": u["src"], "day": u["day"], "entry_t": u["entry_t"],
                                                      "dir": u["dir"], "why": why}]


def _decide(S: dict, u: dict, lit, armed_by_day, now):
    """One candidate at its entry: tools/second_mix.play_day's checks + no-hedge + engine/account_b.qty (weights)."""
    from . import account_b as AB
    ev, R = S["ev"], rules()
    why = None
    if ev["failed"]:
        why = "eval failed today: a new eval from the next session"
    elif float(ev["cum"]) <= -float(R["dll"]):
        why = f"soft daily loss ${float(R['dll']):,.0f} reached today"
    elif u["entry_t"] < int(ev["busy"]):
        why = "one position at a time"
    elif int(ev["nd"]) >= MAX_DAY:
        why = f"{MAX_DAY} trades today already"
    else:
        why = _hedge_why(u, lit, armed_by_day)
    q, reasons = 0, []
    if not why:
        sz = AB.qty(spec(S.get("start_day")), {"risk_pts": u["risk"], "tgt_pts": u["tgt"]}, _state_for_size(S), key=u["key"])
        q, reasons = int(sz.get("qty") or 0), [str(x)[:120] for x in (sz.get("reasons") or [])][-4:]
        if q <= 0:
            why = "size 0 (" + "; ".join(reasons[-2:]) + ")"
    if why:
        _skip(S, u, why)
        return
    w = AB.weight(spec(), u["key"])
    row = {"id": u["id"], "key": u["key"], "src": u["src"], "short": SHORT[u["src"]], "day": u["day"], "entry_t": u["entry_t"],
           "dir": u["dir"], "side": _side(u["dir"]), "entry": u.get("entry"), "stop": u.get("stop"), "target": u.get("target"), "qty": q,
           "weight": w, "risk_pts": u["risk"], "risk_usd": round(u["risk"] * PV * q, 2), "exit_t": None, "exit_kind": "OPEN",
           "usd": None, "r": None, "eval": ev["n"], "session": ev["sess"], "decided_t": int(now), "size": reasons[-2:]}
    S["ledger"][u["id"]] = row
    S["open"] = u["id"]
    ev["nd"] = int(ev["nd"]) + 1
    ev["busy"] = INF


def _resolve(S: dict, units: dict, lit, now) -> bool:
    """Book the open shadow trade when its member's trade has finished or LIT entered the other way (HEDGE). True = no
    trade open any more."""
    oid = S.get("open")
    if not oid:
        return True
    row, u = S["ledger"].get(oid), units.get(oid)
    if row is None:
        S["open"] = None
        return True
    if u is None:
        return False                                         # the member's row is not in this poll's data: wait
    end = u["exit_t"] if not u["open"] else int(now)
    opp = [x["entry_t"] for x in lit if x["day"] == u["day"] and x["dir"] != u["dir"] and u["entry_t"] < x["entry_t"] < end]
    if u["open"] and not opp:
        return False
    ev, R = S["ev"], rules()
    q = int(row["qty"])
    if opp:
        nxt = min(opp)
        pts, w1 = cut_at(u, nxt)
        if pts is None:
            return False                                     # the bar at LIT's entry is not in the data yet
        ex, xt = "HEDGE", nxt
    else:
        pts, w1, ex, xt = u["pts"], u["w1"], u["exit"], u["exit_t"]
    from .sizing import TW_COMM
    pnl = pts * PV * q - TW_COMM * q
    low = min(0.0, w1 * PV * q - TW_COMM * q, pnl)
    if float(ev["cum"]) + low <= -float(R["dll"]):
        pnl = -float(R["dll"]) - float(ev["cum"]) - SLIP * PV * q
        low = pnl
    row.update(exit_t=int(xt), exit_kind=ex, usd=round(pnl, 2), low=round(low, 2),
               r=round(pnl / row["risk_usd"], 3) if row["risk_usd"] else 0.0, booked_t=int(now))
    ev["busy"] = int(xt)
    if float(ev["bal"]) + float(ev["cum"]) + low <= float(ev["floor"]):
        ev["failed"] = True
        ev["cum"] = float(ev["cum"]) + pnl                   # display only: the eval ends FAIL at this session's close
        row["note"] = "eval FAILED on this trade"
    else:
        ev["cum"] = float(ev["cum"]) + pnl
    S["open"] = None
    return True


def advance(S: dict, units: list, lit: list, armed: list, sessions: list, now: int) -> dict:
    """One poll: decide the new candidates in entry order (member priority EMA > MACD > S/R > Asia hunt > trend hunt),
    book the open trade when it is done, close the finished sessions. units = unit_of() of every member trade known now."""
    now = int(now)
    S["t"] = now
    seen = set(S.get("seen") or [])
    byid = {u["id"]: u for u in units}
    pr = {k: i for i, k in enumerate(SPEC["strategies"])}
    A = {}
    for a in armed or []:
        A.setdefault(a[0], []).append(tuple(a))
    lit = sorted(lit or [], key=lambda x: x["entry_t"])
    todo = sorted((u for u in units if u["id"] not in seen and u["entry_t"] >= int(S["first_run"]) - 300 and u["entry_t"] <= now),
                  key=lambda u: (u["entry_t"], pr.get(u["key"], 9)))
    for u in todo:
        if not _resolve(S, byid, lit, now):
            break
        cur = S["ev"]["day"] or S.get("last_day")
        seen.add(u["id"])
        if cur and (u["day"] < cur or (S["ev"]["day"] is None and u["day"] == cur)):
            _skip(S, u, "seen after a later session started (late data): not traded")
            continue
        if u["day"] not in sessions:
            sessions = sorted(set(sessions) | {u["day"]})
        _goto(S, u["day"], sessions)
        _decide(S, u, lit, A, now)
    _resolve(S, byid, lit, now)
    close_through(S, trading_day(now), sessions)
    S["seen"] = sorted(seen, key=lambda k: int(k.split(":")[1]))[-3000:]
    if len(S["ledger"]) > 400:
        S["ledger"] = dict(sorted(S["ledger"].items(), key=lambda kv: kv[1]["entry_t"])[-400:])
    return S


def sessions_of(df5, since_day: str | None = None) -> list:
    """The trading days of a 5m frame (18:00 ET opens the next day), from since_day on."""
    import pandas as pd
    if df5 is None or not len(df5):
        return []
    t = pd.to_datetime(df5["time"].astype("int64"), unit="s", utc=True).dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)
    days = sorted(set(t.dt.strftime("%Y-%m-%d")))
    days = [d for d in days if _dt.date.fromisoformat(d).weekday() < 5]
    return [d for d in days if not since_day or d >= since_day]


def members_rows(block: dict | None, ledger: bool = True) -> dict:
    """{member key: [trade rows]} from engine/second.ledger_update's block (cloud: frozen ledgers) or from a run()
    (PC: its window's trades)."""
    out = {}
    for k in SPEC["strategies"]:
        s = ((block or {}).get("strategies") or {}).get(k) or {}
        out[k] = list((s.get("ledger") or {}).values()) if ledger and s.get("ledger") is not None else list(s.get("trades") or [])
    return out


def step(prev: dict | None, rows_by_key: dict, res: dict | None, df5, df1, now: int, first_run: int | None = None) -> dict:
    """The live step (cloud and PC): prev state (None = start now), the members' paper trades, LIT's run of the same bars,
    the bars. Never routes anything. Raises only on a programming error (callers catch)."""
    if isinstance(prev, dict) and prev.get("v") == VERSION and prev.get("ev"):
        S = json.loads(json.dumps(prev, default=str))       # a failing step never leaves a half-updated state behind
        S.pop("error", None)
    else:
        S = new_state(now, first_run)
    B1 = Bars(df1, 60) if df1 is not None and len(df1) else None
    B5 = Bars(df5, 300) if df5 is not None and len(df5) else None
    units = []
    for k, rows in (rows_by_key or {}).items():
        for r in rows:
            u = unit_of(r, k, B1, B5)
            if u is not None:
                units.append(u)
    lit, armed = lit_inputs(res, now, S.get("armed"))
    S["armed"] = armed
    advance(S, units, lit, armed, sessions_of(df5, S["start_day"]), now)
    return S


# ---------------------------------------------------------------------------------------------------------------- views
def eval_view(S: dict | None) -> dict:
    R = rules()
    start = float(R["start"])
    if not S:
        return {"status": "not started", "start_balance": start, "target": start + float(R["target"])}
    ev = S["ev"]
    bal = float(ev["bal"]) + float(ev["cum"])
    room = bal - float(ev["floor"])
    status = "failed today" if ev["failed"] else "open"
    return {"n": ev["n"], "start": ev["start"], "session": ev["sess"], "day": ev["day"], "start_balance": start,
            "balance": round(start + bal, 2), "profit": round(bal, 2), "today": round(float(ev["cum"]), 2),
            "floor": round(start + float(ev["floor"]), 2), "room": round(room, 2), "target": start + float(R["target"]),
            "to_target": round(max(0.0, float(R["target"]) - bal), 2), "progress": round(max(0.0, min(1.0, bal / float(R["target"]))), 3),
            "status": status, "min_room": float(spec()["min_room"]), "dll": float(R["dll"]), "plan": "MFFU Builder 25K", "price": PRICE}


def money(S: dict | None) -> dict:
    rows = [r for r in (S or {}).get("ledger", {}).values() if r.get("exit_kind") not in (None, "OPEN")]
    E = (S or {}).get("evals") or []
    bought = len(E) + 1 if S else 0
    usd = round(sum(float(r.get("usd") or 0) for r in rows), 2)
    days = max(1, len({r["day"] for r in rows})) if rows else 1
    first = (S or {}).get("start_day")
    months = None
    if first and S.get("t"):
        months = max(1.0 / 21.0, ((_dt.date.fromisoformat(trading_day(S["t"])) - _dt.date.fromisoformat(first)).days + 1) / 30.4)
    return {"n": len(rows), "hunts_n": sum(1 for r in rows if r["src"] in HUNTS), "usd": usd,
            "wins": sum(1 for r in rows if float(r.get("usd") or 0) > 0),
            "by_member": {s: [sum(1 for r in rows if r["src"] == s), round(sum(float(r.get("usd") or 0) for r in rows if r["src"] == s), 2)]
                          for s in SHORT},
            "evals_bought": bought, "fees": round(PRICE * bought, 2), "net_less_fees": round(usd - PRICE * bought, 2),
            "per_month": round((usd - PRICE * bought) / months) if months else None,
            "passes": sum(1 for e in E if e["result"] == "PASS"), "fails": sum(1 for e in E if e["result"] == "FAIL"),
            "stuck": sum(1 for e in E if e["result"] == "STUCK"), "days_traded": days if rows else 0}


def compact(S: dict | None, n: int = 6) -> dict | None:
    """The heartbeat cut (PC "second.atlas_v2"): eval, money, the open trade, the last trades. Small."""
    if not S:
        return None
    rows = sorted(S.get("ledger", {}).values(), key=lambda r: r["entry_t"])
    keep = ("id", "src", "short", "day", "entry_t", "exit_t", "dir", "qty", "entry", "stop", "target", "exit_kind", "usd", "r", "eval")
    return {"v": VERSION, "t": S.get("t"), "first_run": S.get("first_run"), "label": LABEL, "paper": True, "never_routed": True,
            "eval": eval_view(S), "money": money(S), "open": S.get("open"),
            "trades": [{k: r.get(k) for k in keep} for r in rows[-n:]], "evals": (S.get("evals") or [])[-6:]}


# ---------------------------------------------------------------------------------------------------------------- scorecard
def build(path: str = BAND_PATH) -> dict:
    """Bootstrap bands from the research run's path trades (2026 H2 = expected, 2025 = bad year), like
    engine/second_scorecard: "hunts" (SHA + SHT trades at their real size, R = $ / $ at risk) and "account" (every trade)."""
    from . import second_scorecard as SC
    from tools import runlib as rl
    d = rl.load(RUN)
    cols = d["trade_cols"]
    T = [dict(zip(cols, t)) for t in d["trades"]]
    pools = {}
    for nm, (a, z) in SC.SPANS.items():
        span = [t for t in T if a <= t["day"] <= z]
        pools.setdefault("hunts", {})[nm] = [(float(t["r"]), float(t["pnl"])) for t in span if t["trigger"] in HUNTS]
        pools.setdefault("account", {})[nm] = [(float(t["r"]), float(t["pnl"])) for t in span]
    out = {"version": VERSION, "run": RUN, "spans": SC.SPANS, "ready_n": SC.READY_N, "qs": SC.QS, "bands": {},
           "note": "R = $ / $ at risk at the shadow's real size (need size, hunts at 0.5); $ per trade at that size"}
    for i, (k, P) in enumerate(pools.items()):
        out["bands"][k] = {nm: SC._band(P[nm], SC.SEED + 1000 + 17 * i + j) for j, nm in enumerate(SC.SPANS)}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


def load_bands(path: str = BAND_PATH) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


RULE = ("Decide after 20+ hunt trades (Asia + trend hunt) in the shadow: their cumulative R inside the expected range (the "
        "research path's 2026 H2 bootstrap, at or above its p10) = the hunts behave like the research; under its p5 = keep "
        "ATLAS as it is. The account line compares every shadow trade's $ with the same band.")


def scorecard(S: dict | None, bands: dict | None = None) -> dict:
    from . import second_scorecard as SC
    bands = bands if bands is not None else (load_bands() or {})
    B = bands.get("bands") or {}
    rows = [{**r, "usd": r.get("usd")} for r in (S or {}).get("ledger", {}).values()]
    hunts = [r for r in rows if r.get("src") in HUNTS]
    return {"hunts": SC.verdict(B.get("hunts"), hunts), "account": SC.verdict(B.get("account"), rows, ready_n=40),
            "rule": RULE, "built": bool(B), "run": bands.get("run")}


def card(state: dict | None = None, pc: dict | None = None, bands: dict | None = None, src: str | None = None) -> dict:
    """data.json second.atlas_v2 / /api/next/second atlas_v2: the dashboard card (read-only). state = a full shadow state
    (the cloud's; the PC page passes its own with src="PC"); pc = the PC heartbeat's compact (used when the cloud has none
    or is an hour+ older)."""
    state = state if isinstance(state, dict) and state.get("ev") else None
    pc = pc if isinstance(pc, dict) and pc.get("eval") else None
    use_pc = bool(pc) and (not state or int((pc or {}).get("t") or 0) > int((state or {}).get("t") or 0) + 3600)
    src = "PC" if use_pc else (src or "cloud") if state else None
    S = state if not use_pc else None
    out = {"label": LABEL, "paper": True, "never_routed": True, "source": src, "run": RUN, "writeup": "atlas-v2",
           "what": "ATLAS + the two stop hunts (Asia resweep, trend inducement) at half size + buy a new eval when the room is "
                   "under $200, on its own simulated Builder 25K, on the same bars as the live ATLAS. Paper only: never routed.",
           "members": [SHORT[SRC[k]] + (" x0.5" if k in SPEC["weights"] else "") for k in SPEC["strategies"]],
           "research": RESEARCH, "today_research": TODAY, "first_run": (state or pc or {}).get("first_run")}
    if use_pc:
        out.update(eval=pc.get("eval"), money=pc.get("money"), trades=pc.get("trades") or [], evals=pc.get("evals") or [], t=pc.get("t"))
        out["scorecard"] = scorecard({"ledger": {str(i): r for i, r in enumerate(pc.get("trades") or [])}}, bands)
        out["scorecard"]["note"] = "from the PC's last trades only (the cloud ledger has the full count)"
    elif S:
        rows = sorted(S.get("ledger", {}).values(), key=lambda r: r["entry_t"])
        out.update(eval=eval_view(S), money=money(S), trades=rows[-40:], evals=(S.get("evals") or [])[-20:], t=S.get("t"),
                   skipped=(S.get("skipped") or [])[-12:], scorecard=scorecard(S, bands))
    else:
        out.update(eval=eval_view(None), money=money(None), trades=[], evals=[], scorecard=scorecard(None, bands),
                   text="waiting for the first cloud run with the shadow")
    m, sc = out.get("money") or {}, (out.get("scorecard") or {}).get("hunts") or {}
    out["progress"] = {"hunts_n": int(m.get("hunts_n") or 0), "need": int(sc.get("need") or 20), "text": sc.get("text")}
    return out


def notices(S: dict | None, since: int, money_fmt=None) -> list:
    """Push payloads (kind "second", "ATLAS v2 PAPER ...") for each new shadow entry / exit / eval end after `since`."""
    from . import push
    fm = money_fmt or (lambda x: ("+" if x >= 0 else "-") + f"${abs(x):,.0f}")
    out = []
    for r in (S or {}).get("ledger", {}).values():
        et_ = int(r["entry_t"])
        dt_ = int(r.get("decided_t") or et_)
        if dt_ >= since:
            px = lambda v: f"{float(v):,.2f}" if _num(v) is not None else "?"
            p = push.text_payload("Cloud", "second", f"ATLAS v2 PAPER {r['short']} {r['side']}",
                                  f"Shadow entry {r['qty']} MNQ at {px(r.get('entry'))}, stop {px(r.get('stop'))}"
                                  + (f", target {px(r['target'])}" if r.get("target") is not None else "")
                                  + f" (eval {r['eval']}, session {r['session']}). Paper shadow, never traded.",
                                  key=f"atlas_v2:fill:{r['id']}", t=dt_, url="#/atlas")
            out.append({**p, "side": r["side"], "entry": r["entry"], "stop": r["stop"], "target": r.get("target"), "qty": r["qty"],
                        "setup": LABEL})
        bt = int(r.get("booked_t") or 0)
        if r.get("exit_kind") not in (None, "OPEN") and bt >= since:
            p = push.text_payload("Cloud", "second", f"ATLAS v2 PAPER {r['short']} {r['side']} {r['exit_kind']}",
                                  f"{fm(float(r.get('usd') or 0))} on paper ({float(r.get('r') or 0):+.2f}R). Shadow, never traded.",
                                  key=f"atlas_v2:out:{r['id']}", t=bt, url="#/atlas")
            out.append({**p, "side": r["side"], "usd": r.get("usd"), "exit": r.get("exit_kind"), "setup": LABEL})
    for e in (S or {}).get("events") or []:
        if e.get("kind") == "eval" and int(e.get("t") or 0) >= since:
            p = push.text_payload("Cloud", "second", f"ATLAS v2 PAPER eval {e['n']} {e['result']}",
                                  f"Shadow 25K eval {e['n']}: {e['result']} after {e['sessions']} sessions ({fm(float(e['profit']))}); "
                                  "the shadow buys the next one ($63, paper).", key=f"atlas_v2:eval:{e['n']}:{e['result']}", t=int(e["t"]), url="#/atlas")
            out.append(p)
    return sorted(out, key=lambda n: n["t"])


def readme_lines(S: dict | None) -> list:
    if not S:
        return []
    ev, m = eval_view(S), money(S)
    sc = scorecard(S)["hunts"]
    return ["", f"### {LABEL}",
            f"Candidate 1b of research/writeups/atlas-v2.md on a simulated Builder 25K next to the live ATLAS. Paper only, never routed.",
            f"- Eval {ev.get('n')}: session {ev.get('session')}, balance ${ev.get('balance', 0):,.0f}, room ${ev.get('room', 0):,.0f}, "
            f"${ev.get('to_target', 0):,.0f} to pass.",
            f"- {m['n']} trades ({m['hunts_n']} hunt trades), ${m['usd']:+,.0f} on paper, ${m['net_less_fees']:+,.0f} after {m['evals_bought']} x $63; "
            f"passes {m['passes']}, fails {m['fails']}, stuck {m['stuck']}.",
            f"- Hunts scorecard: {sc.get('text')}."]


# ---------------------------------------------------------------------------------------------------------------- PC
def pc_path(bot_state_path: str | None) -> str:
    d = os.path.dirname(bot_state_path) if bot_state_path else os.path.join(ROOT, "data")
    return os.path.join(d, "live_state_atlas_v2.json")


def pc_step(path: str, second_run: dict | None, res: dict | None, df5, df1, now: int) -> dict | None:
    """The PC bot's paper thread (LiveBot._second_tick): one step on its own second run, saved to `path`. Never raises."""
    try:
        if not enabled():
            return None
        prev = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                prev = json.load(fh)
        S = step(prev, members_rows(second_run, ledger=False), res, df5, df1, now)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(S, fh, separators=(",", ":"), default=str)
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, path)
        return S
    except Exception as e:
        return {"v": VERSION, "error": f"{e.__class__.__name__}: {e}"}


def main(argv=None):
    import sys
    a = (argv if argv is not None else sys.argv[1:]) or ["show"]
    if a[0] == "build":
        o = build()
        for k, b in o["bands"].items():
            e = b["expected"]["by_n"]["20"]
            print(k, "pool", b["expected"]["n_pool"], "/", b["bad_year"]["n_pool"], "| after 20: cum R p5/p50/p90",
                  e["cum_r_q"][1], e["cum_r_q"][10], e["cum_r_q"][18], "| $ p10/p50/p90", e["usd"])
        return 0
    p = os.path.join(ROOT, "data", "cloud_state.json")
    st = json.load(open(p, encoding="utf-8")).get("atlas_v2") if os.path.exists(p) else None
    print(json.dumps(card(st), indent=1, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
