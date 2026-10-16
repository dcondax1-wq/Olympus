"""Pine vs Python parity: TradingView Strategy Tester "List of trades" CSV  <->  engine.backtest trades.

    python -X utf8 tools/pine_parity.py <tv_trades.csv> [--tz America/New_York] [--params '{"risk_usd": 350}']
                                        [--from 2026-08-06 --to 2026-10-13] [--tol-min 10] [--r-tol 0.3]
    python -X utf8 tools/pine_parity.py --selftest      # builds a synthetic TV export from the Python trades

Export on TradingView: Strategy Tester > List of trades > Export (CSV). Set the chart timezone to New York (or pass
--tz with the chart's timezone: the export's Date/Time column is in the chart timezone).

Matching: same side and entry time within --tol-min minutes (nearest wins). For every match the exit-reason class
(TARGET / STOP / BE / TIME / TIMESTOP / GIVEBACK / SIGNAL) and the gross R (points moved / planned risk points) are
compared. Parity score = full matches / (python + tradingview - entry matches), i.e. the Jaccard overlap of the two
trade lists counting a trade only when entry, side and exit class agree and R is within --r-tol.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
DATE_FMTS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%b %d, %Y, %H:%M",
             "%b %d, %Y %H:%M", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M", "%Y/%m/%d %H:%M")


# ------------------------------------------------------------------------------------------------ classification
def py_class(reason: str) -> str:
    r = (reason or "").upper()
    if r == "TARGET":
        return "TARGET"
    if r == "STOP":
        return "STOP"
    if r.startswith("BE") or "TRAIL" in r:
        return "BE"
    if r == "TIME STOP":
        return "TIMESTOP"
    if r in ("TIME", "EOD", "NEWS FLAT", "TIME SAFETY", "FLAT"):
        return "TIME"
    if "GIVEBACK" in r:
        return "GIVEBACK"
    return "SIGNAL"


def tv_class(signal: str, r_gross: float | None) -> str:
    s = (signal or "").upper().strip()
    if "TARGET" in s:
        return "TARGET"
    if "TIME STOP" in s:
        return "TIMESTOP"
    if "GIVEBACK" in s:
        return "GIVEBACK"
    if "FLAT" in s or "CLOSE" in s:          # "FLAT", "NEWS FLAT", TradingView's default close-all comment
        return "TIME"
    if "STOP" in s or s in ("XL", "XS", ""):
        if s in ("XL", "XS", "") and r_gross is not None and r_gross > 0.5:
            return "TARGET"                   # bracket exit without comment_profit/loss: infer from the result
        return "BE" if (r_gross is not None and r_gross > -0.15) else "STOP"
    return "SIGNAL"


# ------------------------------------------------------------------------------------------------ TradingView CSV
def _parse_time(s: str, tz: ZoneInfo) -> int:
    s = s.strip()
    for f in DATE_FMTS:
        try:
            return int(dt.datetime.strptime(s, f).replace(tzinfo=tz).timestamp())
        except ValueError:
            continue
    raise ValueError(f"unrecognised Date/Time {s!r}")


def _num(s) -> float | None:
    if s is None:
        return None
    s = str(s).replace(",", "").replace("$", "").replace("USD", "").replace("−", "-").strip()
    try:
        return float(s)
    except ValueError:
        return None


def read_tv(path: str, tz: str = "America/New_York") -> list[dict]:
    """One dict per round trip: entry_t, dir, entry, exit, qty, profit, entry_signal, exit_signal, risk_pts (from 'r=')."""
    zone = ZoneInfo(tz)
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    cols = {k.lower().strip(): k for k in rows[0].keys()}

    def col(*cands, contains=None):
        for c in cands:
            if c in cols:
                return cols[c]
        if contains:
            for k, v in cols.items():
                if all(x in k for x in contains):
                    return v
        return None
    c_no = col("trade #", "trade", "trade number", contains=("trade",))
    c_type = col("type")
    c_sig = col("signal")
    c_time = col("date/time", "date and time", "date", contains=("date",))
    c_px = col("price usd", "price", contains=("price",))
    c_qty = col("contracts", "quantity", "qty", "size (qty)", "position size (qty)", contains=("qty",)) or col(contains=("contract",))
    c_pnl = col("profit usd", "profit", "net p&l usd", "net p&l", contains=("p&l",)) or col(contains=("profit",))
    if not (c_no and c_type and c_time and c_px):
        raise ValueError(f"not a TradingView 'List of trades' export (columns: {list(rows[0].keys())})")
    trades: dict[str, dict] = {}
    for r in rows:
        no = str(r[c_no]).strip()
        typ = str(r[c_type]).lower()
        t = trades.setdefault(no, {"no": no})
        side = 1 if "long" in typ else (-1 if "short" in typ else 0)
        if side:
            t["dir"] = side
        if "entry" in typ:
            t["entry_t"] = _parse_time(r[c_time], zone)
            t["entry"] = _num(r[c_px])
            t["entry_signal"] = (r.get(c_sig) or "").strip() if c_sig else ""
            t["qty"] = _num(r.get(c_qty)) if c_qty else None
        elif "exit" in typ:
            t["exit_t"] = _parse_time(r[c_time], zone) if str(r[c_time]).strip() else None
            t["exit"] = _num(r[c_px])
            t["exit_signal"] = (r.get(c_sig) or "").strip() if c_sig else ""
            t["profit"] = _num(r.get(c_pnl)) if c_pnl else None
    out = []
    for t in trades.values():
        if "entry_t" not in t or "dir" not in t:
            continue
        m = re.search(r"r=([0-9.]+)", t.get("entry_signal", ""))
        t["risk_pts"] = float(m.group(1)) if m else None
        out.append(t)
    return sorted(out, key=lambda x: x["entry_t"])


# ------------------------------------------------------------------------------------------------ Python side
def py_trades(params: dict | None = None) -> list[dict]:
    from engine.backtest import run
    res = run("NQ", "5m", params or {}, light=True)
    out = []
    for t in res["trades"]:
        out.append({"entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "entry": float(t["entry"]), "exit": float(t["exit_price"]),
                    "exit_t": int(t["exit_t"]), "risk_pts": float(t["risk_pts"]), "qty": int(t["qty"]),
                    "reason": t["exit_reason"], "grade": t.get("grade"), "pnl_r": float(t["pnl_r"])})
    return out


def _day(ts: int) -> str:
    return (dt.datetime.fromtimestamp(ts, ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------------ compare
def compare(py: list[dict], tv: list[dict], tol_min: float = 10, r_tol: float = 0.3, day_from=None, day_to=None,
            verbose=True) -> dict:
    if tv and day_from is None:
        day_from = _day(min(t["entry_t"] for t in tv))
    if tv and day_to is None:
        day_to = _day(max(t["entry_t"] for t in tv))
    py = [t for t in py if (day_from is None or _day(t["entry_t"]) >= day_from) and (day_to is None or _day(t["entry_t"]) <= day_to)]
    used = set()
    rows = []
    for p in py:
        best, bd = None, None
        for j, t in enumerate(tv):
            if j in used or t["dir"] != p["dir"]:
                continue
            d = abs(t["entry_t"] - p["entry_t"])
            if d <= tol_min * 60 and (bd is None or d < bd):
                best, bd = j, d
        pr = (p["exit"] - p["entry"]) * p["dir"] / p["risk_pts"]
        pc = py_class(p["reason"])
        if best is None:
            rows.append({"t": p["entry_t"], "dir": p["dir"], "py": pc, "py_r": pr, "tv": None, "tv_r": None, "dt": None, "status": "PY ONLY"})
            continue
        used.add(best)
        t = tv[best]
        risk = t.get("risk_pts") or p["risk_pts"]
        tr = (t["exit"] - t["entry"]) * t["dir"] / risk if t.get("exit") is not None and risk else None
        tc = tv_class(t.get("exit_signal", ""), tr)
        status = "MATCH"
        if tc != pc:
            status = "EXIT DIFF"
        elif tr is None or abs(tr - pr) > r_tol:
            status = "R DIFF"
        rows.append({"t": p["entry_t"], "dir": p["dir"], "py": pc, "py_r": pr, "tv": tc, "tv_r": tr, "dt": (t["entry_t"] - p["entry_t"]) // 60,
                     "status": status})
    for j, t in enumerate(tv):
        if j in used:
            continue
        risk = t.get("risk_pts")
        tr = (t["exit"] - t["entry"]) * t["dir"] / risk if t.get("exit") is not None and risk else None
        rows.append({"t": t["entry_t"], "dir": t["dir"], "py": None, "py_r": None, "tv": tv_class(t.get("exit_signal", ""), tr),
                     "tv_r": tr, "dt": None, "status": "TV ONLY"})
    rows.sort(key=lambda r: r["t"])
    n_py, n_tv = len(py), len(tv)
    entry_m = sum(1 for r in rows if r["status"] in ("MATCH", "EXIT DIFF", "R DIFF"))
    full_m = sum(1 for r in rows if r["status"] == "MATCH")
    denom = n_py + n_tv - entry_m
    out = {"n_py": n_py, "n_tv": n_tv, "entry_matches": entry_m, "full_matches": full_m,
           "entry_parity": round(entry_m / denom, 3) if denom else 1.0, "parity": round(full_m / denom, 3) if denom else 1.0,
           "window": [day_from, day_to], "rows": rows}
    if verbose:
        f = lambda x: "" if x is None else f"{x:+.2f}"
        print(f"Window {day_from} .. {day_to} | python {n_py} trades | tradingview {n_tv} trades")
        print(f"{'entry (ET)':17} {'side':5} {'python':9} {'R':>6}   {'tradingview':11} {'R':>6} {'dt':>4}  status")
        for r in rows:
            print(f"{dt.datetime.fromtimestamp(r['t'], ET):%Y-%m-%d %H:%M} {'L' if r['dir'] == 1 else 'S':5} {r['py'] or '-':9} {f(r['py_r']):>6}   "
                  f"{r['tv'] or '-':11} {f(r['tv_r']):>6} {'' if r['dt'] is None else r['dt']:>4}  {r['status']}")
        print(f"Entry parity {out['entry_parity']:.0%} ({entry_m} matched) | full parity {out['parity']:.0%} "
              f"({full_m} with the same exit class and R within {r_tol})")
    return out


# ------------------------------------------------------------------------------------------------ synthetic self-test
def write_tv_csv(path: str, trades: list[dict], tz: str = "America/New_York"):
    """Write trades in TradingView's 'List of trades' layout (newest first, Exit row above Entry row)."""
    zone = ZoneInfo(tz)
    hdr = ["Trade #", "Type", "Signal", "Date/Time", "Price USD", "Contracts", "Profit USD", "Profit %", "Cum. Profit USD",
           "Cum. Profit %", "Run-up USD", "Run-up %", "Drawdown USD", "Drawdown %"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        cum = 0.0
        rows = []
        for n, t in enumerate(trades, 1):
            side = "long" if t["dir"] == 1 else "short"
            pnl = (t["exit"] - t["entry"]) * t["dir"] * 2.0 * t["qty"] - 1.5 * t["qty"]
            cum += pnl
            ts = lambda x: dt.datetime.fromtimestamp(x, zone).strftime("%Y-%m-%d %H:%M")
            rows.append([[n, f"Exit {side}", t["exit_signal"], ts(t["exit_t"]), f"{t['exit']:.2f}", t["qty"], f"{pnl:.2f}", "", f"{cum:.2f}", "", "", "", "", ""],
                         [n, f"Entry {side}", t["entry_signal"], ts(t["entry_t"]), f"{t['entry']:.2f}", t["qty"], f"{pnl:.2f}", "", f"{cum:.2f}", "", "", "", "", ""]])
        for pair in reversed(rows):
            w.writerows(pair)


def _tv_signal_for(reason: str) -> str:
    c = py_class(reason)
    return {"TARGET": "TARGET", "STOP": "STOP", "BE": "STOP", "TIMESTOP": "TIME STOP", "GIVEBACK": "GIVEBACK",
            "TIME": "FLAT"}.get(c, "SIGNAL")


def selftest() -> bool:
    py = py_trades()
    assert len(py) >= 6, f"need >= 6 python trades for the self-test, got {len(py)}"
    syn = []
    for k, p in enumerate(py):
        t = {"dir": p["dir"], "entry_t": p["entry_t"], "entry": p["entry"], "exit": p["exit"], "exit_t": p["exit_t"], "qty": p["qty"],
             "entry_signal": f"{'L' if p['dir'] == 1 else 'S'} r={p['risk_pts']:.2f} g={p['grade']}", "exit_signal": _tv_signal_for(p["reason"])}
        if k == 1:
            t["entry_t"] += 300                                        # TV filled one bar later: still an entry match
        if k == 2:
            continue                                                   # TV missed this trade -> PY ONLY
        if k == 3:
            t["exit_signal"] = "GIVEBACK" if py_class(p["reason"]) != "GIVEBACK" else "TARGET"   # different exit -> EXIT DIFF
        if k == 4:
            t["exit"] = p["exit"] + p["dir"] * 0.5 * p["risk_pts"]   # same exit class, +0.5R better fill -> R DIFF
        syn.append(t)
    extra = dict(syn[-1])
    extra["entry_t"] = py[-1]["entry_t"] - 3 * 3600                    # TV-only trade 3 h earlier the same day
    extra["exit_t"] = extra["entry_t"] + 1800
    extra["dir"] = -py[-1]["dir"]
    extra["exit"] = extra["entry"] - extra["dir"] * 10
    extra["exit_signal"] = "STOP"
    syn.append(extra)
    syn.sort(key=lambda x: x["entry_t"])
    path = os.path.join(tempfile.mkdtemp(prefix="pine_parity_"), "tv_trades.csv")
    write_tv_csv(path, syn)
    tv = read_tv(path)
    assert len(tv) == len(syn), (len(tv), len(syn))
    assert tv[0]["risk_pts"] is not None and tv[0]["entry_signal"].startswith(("L", "S"))
    res = compare(py, tv)
    st = {}
    for r in res["rows"]:
        st[r["status"]] = st.get(r["status"], 0) + 1
    ok = (st.get("PY ONLY") == 1 and st.get("TV ONLY") == 1 and st.get("EXIT DIFF") == 1 and st.get("R DIFF") == 1
          and res["entry_matches"] == len(py) - 1 and res["full_matches"] == len(py) - 3)          # k=2 missing, k=3 exit diff, k=4 R diff
    # the shifted entry (k=1) must still be a full match
    shifted = next(r for r in res["rows"] if r["t"] == py[1]["entry_t"])
    ok = ok and shifted["status"] == "MATCH" and shifted["dt"] == 5
    print(f"\nself-test statuses {st} -> {'PASS' if ok else 'FAIL'}  (csv: {path})")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--params", default="{}", help="JSON engine params for the Python run (default: DEFAULTS)")
    ap.add_argument("--from", dest="day_from")
    ap.add_argument("--to", dest="day_to")
    ap.add_argument("--tol-min", type=float, default=10)
    ap.add_argument("--r-tol", type=float, default=0.3)
    ap.add_argument("--json", help="also write the result rows to this JSON file")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not a.csv:
        ap.error("csv path required (or --selftest)")
    tv = read_tv(a.csv, a.tz)
    res = compare(py_trades(json.loads(a.params)), tv, a.tol_min, a.r_tol, a.day_from, a.day_to)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
