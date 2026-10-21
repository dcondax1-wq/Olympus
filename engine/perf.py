"""Performance pages (competitor-features #6, 7, 9, 11, 12, 13, 14; 2026-10-21): one read-only view for the PC dashboard
(/api/next/perf) and the phone app (data.json "perf"), built from files the research tools commit and the live state:

  range     engine/health_band.py: is live / paper inside the range the backtest expects (H2 band), the cone for the chart
  exec      live vs backtest on the same days (engine/fill_audit.py rows): two cumulative lines + the gap split into
            slippage, other execution, missed trades and extra trades
  exit      exit efficiency (tools/trade_intel.py exit_eff): % of the best move kept, giveback after +1R, by exit / month
  robust    research/lab/robust.json (tools/lit_robust.py): noisy prices, slippage, missed trades, late entries
  months    research/lab/walkforward.json (tools/lit_walkforward.py) + the paper / PC months and the fill-audit replay months
  status    engine/uptime.py: 30-day uptime per part + incidents
  lookahead research/lab/lookahead_audit.json (tools/lookahead_audit.py): the stored runs' look-ahead check
Nothing here sizes, pauses, routes or changes a setting. Every block is None when its source is missing; never raises.
"""
from __future__ import annotations

import collections
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "research", "lab")
VERSION = 1


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                       # one broken block never breaks the page
        return {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}


# ------------------------------------------------------------------------------------------------ 7. live vs backtest
def exec_curve(rows: list) -> dict | None:
    """engine/fill_audit rows -> per day [day, backtest cum, live cum, backtest $, live $, slippage, other execution, missed,
    extra] and the gap totals. backtest = what the backtest made on the same days at the bot's qty (matched trades) + the
    backtest trades the bot missed; live = what the bot really made (matched + extra)."""
    if not rows:
        return None
    D = collections.OrderedDict()
    for r in sorted(rows, key=lambda r: r.get("entry_t") or 0):
        d = D.setdefault(r["day"], {"bt": 0.0, "live": 0.0, "slip": 0.0, "other": 0.0, "missed": 0.0, "extra": 0.0, "n": 0})
        st = r.get("status")
        if st == "matched":
            bt = r.get("bt_pnl_live_qty") if r.get("bt_pnl_live_qty") is not None else (r.get("bt_pnl") or 0.0)
            lv = r.get("live_pnl") if r.get("live_pnl") is not None else bt + (r.get("exec_usd") or 0.0)
            d["bt"] += bt
            d["live"] += lv
            d["slip"] += r.get("slip_usd") or 0.0
            d["other"] += (lv - bt) - (r.get("slip_usd") or 0.0)
            d["n"] += 1
        elif st == "missed":
            m = r.get("missed_usd") if r.get("missed_usd") is not None else (r.get("bt_pnl") or 0.0)
            d["bt"] += m
            d["missed"] -= m
        elif st == "extra":
            x = r.get("live_pnl") or 0.0
            d["live"] += x
            d["extra"] += x
    out, cb, cl = [], 0.0, 0.0
    for day, d in D.items():
        cb += d["bt"]
        cl += d["live"]
        out.append([day, round(cb, 2), round(cl, 2), round(d["bt"], 2), round(d["live"], 2), round(d["slip"], 2), round(d["other"], 2),
                    round(d["missed"], 2), round(d["extra"], 2)])
    return curve_summary(out, sum(1 for r in rows if r.get("status") == "missed"), sum(1 for r in rows if r.get("status") == "extra"),
                         sum(1 for r in rows if r.get("status") == "matched"),
                         reasons=collections.Counter(str(r.get("reason") or "?").split(":")[0][:60] for r in rows if r.get("status") == "missed"))


COLS = ["day", "bt_cum", "live_cum", "bt", "live", "slip", "other", "missed", "extra"]


def curve_summary(days, n_missed=None, n_extra=None, n_matched=None, reasons=None):
    if not days:
        return None
    g = {k: round(sum(x[i] for x in days), 2) for i, k in enumerate(COLS) if i >= 3}
    gap = round(g["live"] - g["bt"], 2)
    parts = [("slippage", g["slip"]), ("other execution", g["other"]), ("missed trades", g["missed"]), ("extra trades", g["extra"])]
    big = max(parts, key=lambda p: abs(p[1]))
    usd = lambda v: f"{'+' if v >= 0 else '-'}${abs(v):,.0f}"
    text = (f"Since {days[0][0]}: the bot made {usd(g['live'])}, the backtest on the same days {usd(g['bt'])} (gap {usd(gap)}): "
            + ", ".join(f"{k} {usd(v)}" for k, v in parts) + (f". Biggest: {big[0]}." if abs(big[1]) >= 1 else "."))
    return {"cols": COLS, "days": days, "gap": gap, "parts": {k: v for k, v in parts}, "live": g["live"], "bt": g["bt"],
            "matched": n_matched, "missed": n_missed, "extra": n_extra,
            "missed_reasons": dict(reasons.most_common(6)) if reasons else None, "text": text}


def exec_from_hb(ex: dict | None) -> dict | None:
    """The heartbeat's "exec" block (fill_audit.heartbeat_block): its "curve" days, when the PC sends them."""
    if not isinstance(ex, dict) or not ex.get("curve"):
        return None
    c = ex["curve"]
    return curve_summary(c.get("days") or [], c.get("missed"), c.get("extra"), c.get("matched"),
                         collections.Counter(c.get("missed_reasons") or {}))


# ------------------------------------------------------------------------------------------------ 13. months
def months(wf: dict | None, st: dict | None = None, journal=None, exec_c: dict | None = None) -> dict | None:
    """One row per month of 2026 (+ the live months): backtest $ / PF / trades / win %, eval-path $, walk-forward $, paper $,
    PC live $, and the fill audit's replay of the same days."""
    rows = {}
    if wf:
        bt, ep = wf.get("backtest") or {}, wf.get("eval_path") or {}
        wfm = {x["month"]: x for x in (wf.get("walk_forward") or {}).get("months") or []}
        for m in wf.get("months") or []:
            b = bt.get(m) or {}
            rows[m] = {"month": m, "bt": b.get("net"), "bt_pf": b.get("pf"), "bt_n": b.get("n"), "bt_win": b.get("win"),
                       "eval": (ep.get(m) or {}).get("net"), "wf": (wfm.get(m) or {}).get("wf"),
                       "wf_pick_live": (wfm.get(m) or {}).get("pick_is_live")}
    from . import health_band as HB
    paper, live = HB.from_state(st, journal)
    for lab, T in (("paper", paper), ("live", live)):
        for t in T:
            if not t.get("day") or t["day"] < "2026-01-01":
                continue
            m = t["day"][:7]
            x = rows.setdefault(m, {"month": m})
            x[lab] = round((x.get(lab) or 0.0) + float(t.get("usd") or 0.0), 2)
            x[lab + "_n"] = (x.get(lab + "_n") or 0) + 1
    if exec_c:
        for d in exec_c["days"]:
            x = rows.setdefault(d[0][:7], {"month": d[0][:7]})
            x["replay"] = round((x.get("replay") or 0.0) + d[3], 2)
    if not rows:
        return None
    R = [rows[k] for k in sorted(rows)]
    out = {"rows": R, "expect": (wf or {}).get("expect"), "wf": {k: v for k, v in ((wf or {}).get("walk_forward") or {}).items() if k != "months"},
           "batch3b": (wf or {}).get("batch3b"), "text": (wf or {}).get("text"), "method": (wf or {}).get("method"),
           "live_rank": (wf or {}).get("live_rank"), "n_points": (wf or {}).get("n_points")}
    return out


# ------------------------------------------------------------------------------------------------ blocks
def robust(R: dict | None) -> dict | None:
    if not R:
        return None
    keep = ("label", "kind", "reps", "changed")
    tests = {k: {**{kk: v.get(kk) for kk in keep}, **{s: {kk: (v.get(s) or {}).get(kk) for kk in
                                                          ("keep", "keep_p10", "keep_p90", "pf", "pf_p10", "pf_p90", "p10", "p10_lo", "p10_hi",
                                                           "f10", "f10_lo", "f10_hi", "profitable", "net", "tpw")} for s in ("H1", "H2", "2026")}}
             for k, v in (R.get("tests") or {}).items()}
    return {"built": R.get("built"), "card": R.get("card"), "tests": tests, "base": R.get("base"), "method": R.get("method"),
            "same_as_run": R.get("same_as_run")}


def lookahead(L: dict | None, ids=("lit_live", "lit_final", "lit_adopt_t15_be_off")) -> dict | None:
    if not L:
        return None
    from tools import lookahead_audit as LA
    R = L.get("runs") or {}
    return {"built": L.get("built"), "summary": L.get("summary"),
            "badges": {i: LA.badge(R.get(i)) for i in ids if R.get(i)},
            "flagged": [{"id": k, "title": R[k].get("title"), "trades": [{kk: t.get(kk) for kk in ("day", "pnl", "diff")} for t in R[k].get("trades") or []
                                                                          if t.get("status") == "changed"]} for k in (L.get("summary") or {}).get("flagged") or []][:20],
            "method": L.get("method")}


def exit_block(E: dict | None) -> dict | None:
    if not E:
        return None
    return {k: E.get(k) for k in ("text", "y2026", "spans", "by_exit", "by_month", "trades")}


def view(st: dict | None = None, journal=None, exec_rows=None, uptime_state=None, intel_full=None, now=None, compact=False) -> dict:
    """Every Performance block. st: the cloud state (None on the PC); journal: data/lit_journal.jsonl rows; exec_rows: the
    fill audit's rows (the PC) - else the heartbeat's exec curve in st; uptime_state: engine/uptime's store."""
    from . import health_band as HB
    from . import uptime as UP
    now = int(now or time.time())
    B = HB.load()
    out = {"v": VERSION, "t": now}
    out["range"] = _safe(HB.card, B, st, journal, now) if B else None
    ex = _safe(exec_curve, exec_rows) if exec_rows else (exec_from_hb(((st or {}).get("pc") or {}).get("exec")) if st else None)
    out["exec"] = ex
    if intel_full is None:
        intel_full = _read(os.path.join(LAB, "trade_intel.json"))
    E = (intel_full or {}).get("exit_eff")
    if E is None and intel_full:
        from tools import trade_intel as TI
        keys = [c["key"] for c in intel_full["cols"]]
        E = _safe(TI.exit_eff, [dict(zip(keys, r)) for r in intel_full["rows"]])
    out["exit"] = exit_block(E)
    if compact and out["exit"]:
        out["exit"] = {**out["exit"], "trades": [x for x in out["exit"].get("trades") or [] if x[1] != "backtest" or (x[0] or "") >= "2026"][-160:]}
    out["robust"] = robust(_read(os.path.join(LAB, "robust.json")))
    out["months"] = _safe(months, _read(os.path.join(LAB, "walkforward.json")), st, journal, ex if isinstance(ex, dict) and ex.get("days") else None)
    out["status"] = _safe(UP.view, uptime_state, now)
    out["lookahead"] = _safe(lookahead, _read(os.path.join(LAB, "lookahead_audit.json")))
    return out


def pc_view(now=None) -> dict:
    """The PC dashboard: the PC journal's live trades, the fill audit's last report (never re-run here), the PC uptime."""
    from . import fill_audit as FA
    from . import uptime as UP
    J = []
    try:
        from tools.trade_intel import _journal
        J = _journal(os.path.join(ROOT, "data", "lit_journal.jsonl"))
    except Exception:
        pass
    rep = FA._read_json(os.path.join(FA.STORE, "report.json"), None) or {}
    return view(None, J, rep.get("rows") or [], UP._load(UP.PC_PATH), now=now)
