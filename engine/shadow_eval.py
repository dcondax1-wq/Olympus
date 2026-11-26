"""SHADOW EVAL (big-shadow 2026-11-26; research/writeups/business-planner-2026-11-26.md). PAPER ONLY, READ ONLY.

A free, simulated MFFU Builder 50K eval that takes EVERY LIT signal of the live model: the LIT backtest twin of each trading
day on the PC's own bars (engine/fill_audit's nightly replay = engine/lit_live.run, logs/exec_audit/report.json, every row
that is not an "extra"), sized by the live eval sizing (engine/sizing.lit_qty, live_model.json lit_sizing two_week) with the
real MFFU Builder 50K rules: target +$3,000, $2,000 end-of-day trailing max loss that stops at +$100, the $1,000 soft
daily loss (no new entry once the day is down $1,000), min 1 traded day, no consistency rule (Builder eval; a plan with
"cons" checks best day <= cons x profit), $1.90 a micro + 1 tick. A fail (the floor touched, or stuck: 1 micro no longer
fits) restarts a fresh shadow eval the next session; a pass restarts it too (the next attempt). Recomputed from scratch
from the start day on every run (idempotent: same inputs = same answer). It never routes, sizes or changes anything live:
it reads files and writes logs/shadow_eval.json.

What it is for: the buy gate's restart signal (engine/buy_gate.py: "start buying again when a shadow eval passes").
Intraday: the twin rows carry no worst open loss, so a losing trade is counted at its full loss (no deeper dip).

Switch: data/buy_gate.json {"show": true} (default OFF: nothing is computed or shown). Start day: data/shadow_eval.json
{"start": "YYYY-MM-DD"} (written on the first run; gitignored).

    python -X utf8 -m engine.shadow_eval          print the shadow eval (computes even with the switch off)
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import math
import os
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
REPORT = os.path.join(ROOT, "logs", "exec_audit", "report.json")
STATE = os.path.join(ROOT, "data", "shadow_eval.json")
OUT = os.path.join(ROOT, "logs", "shadow_eval.json")
SWITCH = os.path.join(ROOT, "data", "buy_gate.json")
PV, COMM, SLIP = 2.0, 1.90, 0.25
STALE_S = 4 * 86400                    # logs/exec_audit/report.json older than this (a long weekend + 1 day): the shadow says it is stale
PLAN_50K = {"name": "Builder 50K", "target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40,
            "stuck": 200.0, "min_days": 1, "cons": None}


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
    from engine import fsutil   # retries on a Windows / OneDrive lock (test_selfheal)
    fsutil.replace(tmp, path)


def shown(path: str | None = None) -> bool:
    return bool((_read(path or SWITCH, {}) or {}).get("show"))


def today_et(now=None) -> str:
    return dt.datetime.fromtimestamp(int(now if now is not None else time.time()), ET).date().isoformat()


# ------------------------------------------------------------------------------------------------ inputs
def twin_trades(report_path: str | None = None, rows: list | None = None) -> list:
    """LIT backtest twin trades [{day, entry_t, dir, risk, tgt, pts}] in entry order, from fill_audit's report rows."""
    R = rows if rows is not None else ((_read(report_path or REPORT, {}) or {}).get("rows") or [])
    out, seen = [], set()
    for r in R:
        if not isinstance(r, dict) or r.get("status") == "extra":
            continue
        try:
            e, s, x = float(r["bt_entry"]), float(r["bt_stop"]), float(r["bt_exit"])
            d = 1 if str(r.get("side")).upper() == "LONG" else -1
            k = int(r["entry_t"])
        except (KeyError, TypeError, ValueError):
            continue
        risk = abs(e - s)
        if risk <= 0 or k in seen:
            continue
        seen.add(k)
        tg = r.get("bt_target")
        out.append({"day": str(r["day"]), "entry_t": k, "dir": d, "risk": risk,
                    "tgt": abs(float(tg) - e) if tg is not None else None, "pts": (x - e) * d})
    out.sort(key=lambda t: t["entry_t"])
    return out


def sessions(a: str, b: str) -> list:
    """CME trading days a..b (weekdays, full closures out)."""
    try:
        from engine import cme_calendar
        closed = cme_calendar.full_closure
    except Exception:  # noqa: BLE001
        closed = lambda d: False  # noqa: E731
    d, z, out = dt.date.fromisoformat(a), dt.date.fromisoformat(b), []
    while d <= z:
        if d.weekday() < 5 and not closed(d):
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def sizing_cfg(plan: dict) -> dict:
    lm = _read(os.path.join(ROOT, "live_model.json"), {}) or {}
    c = {k: copy.deepcopy(v) for k, v in (lm.get("lit_sizing") or {}).items()
         if k not in ("eval_start", "eval_prior_pnl", "eval_prior_note", "note", "modes", "eval_mode_note", "funded")}
    c["mode"] = "two_week"
    c.setdefault("two_week", {})
    c["two_week"]["acct"] = {k: plan[k] for k in ("target", "mll", "lock", "dll", "max_micros")} | {"scale": 1.0}
    c.pop("learn_costs", None)
    return c


# ------------------------------------------------------------------------------------------------ the eval
def run(trades: list, start: str, end: str, plan: dict | None = None, cfg: dict | None = None) -> dict:
    """Every shadow attempt from `start` to `end` (ISO days). -> {"attempts": [...], "cur": {...}}"""
    from engine import sizing as SZ
    from engine.lit import qty_for
    P = {**PLAN_50K, **(plan or {})}
    C = cfg if cfg is not None else sizing_cfg(P)
    by = {}
    for t in trades:
        by.setdefault(t["day"], []).append(t)
    days = sessions(start, end)
    att, cur = [], None

    def fresh(day):
        return {"start": day, "bal": 0.0, "peak": 0.0, "floor": -P["mll"], "s": 0, "dtr": 0, "best": 0.0, "trades": 0}

    for day in days:
        if cur is None:
            cur = fresh(day)
        cur["s"] += 1
        cum, traded = 0.0, False
        for t in by.get(day, []):
            if cum <= -P["dll"]:
                break
            room = cur["bal"] + cum - cur["floor"]
            st = {"profit": cur["bal"], "cum": cum, "room": room, "session": cur["s"], "n_today": 0, "days_traded": cur["dtr"]}
            m0 = qty_for(t["risk"]) or 1
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, C, room=room, state=st,
                           learning=None, max_micros=P["max_micros"])["qty"]
            q = min(int(q or 0), P["max_micros"])
            if q <= 0:
                continue
            pnl = t["pts"] * PV * q - COMM * q
            if cum + pnl <= -P["dll"]:                     # the soft daily loss: the stop-out is capped there (+1 tick)
                pnl = max(pnl, -P["dll"] - cum - SLIP * PV * q)
            traded, cur["trades"] = True, cur["trades"] + 1
            if cur["bal"] + cum + min(0.0, pnl) <= cur["floor"]:
                cum += pnl
                cur["bal"] += cum
                att.append({**_view(cur, P), "end": day, "result": "fail"})
                cur = None
                break
            cum += pnl
        if cur is None:
            continue
        cur["bal"] += cum
        if traded:
            cur["dtr"] += 1
            cur["best"] = max(cur["best"], cum)
        cur["peak"] = max(cur["peak"], cur["bal"])
        cur["floor"] = min(max(cur["floor"], cur["peak"] - P["mll"]), P["lock"])
        cons_ok = not P.get("cons") or cur["best"] <= P["cons"] * cur["bal"] + 1e-9
        if cur["bal"] >= P["target"] and cur["dtr"] >= P["min_days"] and cons_ok:
            att.append({**_view(cur, P), "end": day, "result": "pass"})
            cur = None
        elif cur["bal"] - cur["floor"] < P["stuck"]:
            att.append({**_view(cur, P), "end": day, "result": "fail"})
            cur = None
    return {"attempts": att, "cur": _view(cur, P) if cur else None, "days": len(days), "plan": P["name"]}


def _view(c, P):
    return {"start": c["start"], "sessions": c["s"], "profit": round(c["bal"], 2), "room": round(c["bal"] - c["floor"], 2),
            "to_pass": round(max(0.0, P["target"] - c["bal"]), 2), "trades": c["trades"], "days_traded": c["dtr"]}


def usd(v) -> str:
    v = float(v or 0)
    return ("-" if v < 0 else "") + f"${abs(v):,.0f}"


def line(res: dict) -> str:
    A = res.get("attempts") or []
    last = A[-1] if A else None
    c = res.get("cur")
    head = (f"Shadow eval (paper {res.get('plan', 'Builder 50K')}): {('+' if c['profit'] >= 0 else '') + usd(c['profit'])}, "
            f"{usd(c['to_pass'])} to pass, room {usd(c['room'])}, session {c['sessions']}") if c else "Shadow eval (paper): starts next session"
    if last:
        head += f" · last: {last['result'].upper()} {last['end']}"
    return head


def refresh(now=None, report_path=None, state_path=None, out_path=None, start: str | None = None, write=True) -> dict:
    """Recompute from the saved start day (set to today on the first run) to today; write logs/shadow_eval.json."""
    sp = state_path or STATE
    st = _read(sp, {}) or {}
    day = today_et(now)
    if start:
        st["start"] = start
    if not st.get("start"):
        st["start"] = day
    if write:
        _write(sp, st)
    res = run(twin_trades(report_path), st["start"], day)
    A = res["attempts"]
    try:                                       # the nightly LIT backtest (engine/fill_audit) feeds the shadow: say so when it stopped
        age = time.time() - os.path.getmtime(report_path or REPORT)
    except OSError:
        age = None
    res["twin_age_h"] = None if age is None else round(age / 3600, 1)
    stale = age is None or age > STALE_S
    res.update(t=int(now if now is not None else time.time()), start=st["start"],
               line=line(res) + (" (no fresh LIT backtest rows: is the nightly fill audit running?)" if stale else ""), stale=stale,
               passes=[a["end"] for a in A if a["result"] == "pass"], fails=sum(1 for a in A if a["result"] == "fail"),
               attempts=A[-10:])
    if write:
        _write(out_path or OUT, res)
    return res


def read(path: str | None = None) -> dict | None:
    return _read(path or OUT, None)


def main() -> int:
    r = refresh(write=False)
    print(r["line"])
    print(f"start {r['start']} · {r['days']} sessions · passes {len(r['passes'])} · fails {r['fails']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
