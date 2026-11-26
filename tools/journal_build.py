"""AUTO TRADE JOURNAL (day-batch7 2026-11-26, lead: "per real trade, an entry with the setup steps, reasons, entry/stop/target, R, $,
MAE/MFE, a chart PNG, and tags; output for the existing journal/ app + a weekly 'what we learned' summary"). Read-only: nothing here
trades, sizes, routes or touches a live setting. Stdlib + pandas (both on the PC), no matplotlib (tools/pngchart.py draws the PNGs).

Inputs (whatever exists; the PC has the first two, the cloud the third):
  1. the bot's ledger rows: engine/datapipe.ledger_rows (data/live_state*.json, logs/exec_audit/ledger.jsonl) + the pipe's archive
     logs/datapipe/ledger_archive.jsonl (the state files keep today only)
  2. the LIT learning journal data/lit_journal.jsonl (source "pc": the swept levels, the setup features, the loss cause)
  3. data/pc_days/days/<day>/trades.jsonl.gz (tools/data_pull.py), already scrubbed
  Bars: the PC's NinjaTrader bars (engine/datapipe.bar_frames: MNQ / NQ 1m) or data/NQ_1m.csv (TradingView CME NQ1!); VIX band from
  data/VIX_1d.csv (the prior close).
A trade = an entry row (side buy / sell, routed ok) + its exit row(s) (side exit, same source and entry_t). Real = mode live / sim
(paper rows only with --all). Account names are masked (engine/datapipe.scrub: "...1234"); no balances.

Outputs:
  tools/web_public/journal/entries.json   {v, built, n, trades: [entry...], weeks: [summary...]} for the journal app
  tools/web_public/journal/charts/<id>.png one 5m chart per trade (entry gold, stop red, target mint, exit white)
  research/journal/week-<YYYY-Www>.md      the weekly "what we learned" (plain words, small-sample warning)
entry = {id, bot, acct, mode, day, week, entry_et, exit_et, side, qty, entry, stop, target, exit_px, risk_pts, risk_usd, usd, r,
         mfe_r, mae_r, held_min, exit, setup: [steps], why: [reasons], tags: {session, vix, tdo, sb_hour, weekday}, chart}

    python -X utf8 tools/journal_build.py                 # build from what this machine has
    PC: tools/pc_report.py runs maybe_run() every 15 min -> once a weekday from 17:20 ET into data/journal/ (gitignored; LE_JOURNAL=0 off)
    python -X utf8 tools/journal_build.py --all           # include paper trades
    python -X utf8 tools/journal_build.py --rows f.jsonl --bars data/NQ_1m.csv --out <dir>   (tests / a one-off file)
Tests: python -X utf8 -m tests.test_journal_build
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys
from collections import defaultdict
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pngchart  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT_DIR = os.path.join(ROOT, "tools", "web_public", "journal")
WEEK_DIR = os.path.join(ROOT, "research", "journal")
PC_DIR = os.path.join(ROOT, "data", "journal")             # gitignored: the PC's nightly build (a tracked-file change would block auto-update)
STATE = os.path.join(ROOT, "data", "journal_build.json")   # gitignored: {"day", "t", "n", "error"}
RUN_FROM = 17 * 60 + 20                                     # ET minutes, weekdays: after engine/datapipe's 17:05 pack
PV, COMM = 2.0, 1.90                     # MNQ $ a point, $ a micro round trip
VIXB = ((0, 15, "<15"), (15, 18, "15-18"), (18, 22, "18-22"), (22, 999, "22+"))
VERSION = 1


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def trading_day(t) -> str:
    e = _et(t)
    d = e.date() + dt.timedelta(days=1) if e.hour >= 18 else e.date()
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def _num(x, d=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else d
    except (TypeError, ValueError):
        return d


# ================================================================================================ inputs
def read_jsonl(path) -> list:
    out = []
    try:
        op = gzip.open if str(path).endswith(".gz") else open
        with op(path, "rt", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def ledger_rows(root: str = ROOT, rows_file: str | None = None) -> list:
    if rows_file:
        return read_jsonl(rows_file)
    rows = []
    try:
        from engine import datapipe as DP
        names = DP.known_names(root)
        rows += [DP.scrub(r, names) for r in DP.ledger_rows(root)]
        rows += [DP.scrub(r, names) for r in read_jsonl(os.path.join(root, "logs", "datapipe", DP.ARCHIVE))]
    except Exception:
        pass
    for p in sorted(glob.glob(os.path.join(root, "data", "pc_days", "days", "*", "trades.jsonl.gz"))):
        rows += read_jsonl(p)
    return rows


def pair(rows: list, include_paper: bool = False) -> list:
    """entry + exit rows -> trades (one per source x entry_t)."""
    ent, ex = {}, defaultdict(list)
    for r in rows:
        if not isinstance(r, dict):
            continue
        if not include_paper and r.get("mode") == "paper":
            continue
        et_ = r.get("entry_t")
        if et_ is None:
            continue
        key = (str(r.get("src") or "main"), int(et_))
        side = r.get("side")
        if side in ("buy", "sell"):
            res = r.get("result") if isinstance(r.get("result"), dict) else {}
            if res.get("ok") is False:
                continue
            ent.setdefault(key, r)
        elif side == "exit":
            ex[key].append(r)
    out = []
    for key, e in ent.items():
        xs = ex.get(key) or []
        if not xs:
            continue                                     # still open (or the exit row not here yet)
        seen, xx = set(), []
        for x in sorted(xs, key=lambda x: int(x.get("t") or 0)):
            k2 = (x.get("t"), x.get("reason"), x.get("qty"))
            if k2 not in seen:
                seen.add(k2)
                xx.append(x)
        out.append((e, xx))
    return sorted(out, key=lambda p: int(p[0]["entry_t"]))


class Bars:
    """1m bars (t = bar open, unix s) from the PC's NinjaTrader frames or a CSV."""

    def __init__(self, path: str | None = None):
        import numpy as np
        import pandas as pd
        df = None
        if path:
            df = pd.read_csv(path)
        else:
            try:
                from engine import datapipe as DP
                fr = DP.bar_frames()
                for root in ("MNQ", "NQ"):
                    if (root, "1m") in fr and len(fr[(root, "1m")]):
                        df = fr[(root, "1m")]
                        break
            except Exception:
                df = None
            if df is None:
                p = os.path.join(ROOT, "data", "NQ_1m.csv")
                df = pd.read_csv(p) if os.path.exists(p) else None
        if df is None or not len(df):
            self.t = np.zeros(0, int)
            self.o = self.h = self.l = self.c = np.zeros(0)
            return
        df = df.sort_values("time")
        self.t = df["time"].to_numpy().astype(int)
        self.o, self.h = df["open"].to_numpy(float), df["high"].to_numpy(float)
        self.l, self.c = df["low"].to_numpy(float), df["close"].to_numpy(float)

    def span(self, a: int, b: int):
        import numpy as np
        i, j = np.searchsorted(self.t, a, "left"), np.searchsorted(self.t, b, "left")
        return i, j

    def open_at(self, t: int):
        i, j = self.span(t, t + 60)
        return float(self.o[i]) if j > i else None

    def candles5(self, a: int, b: int) -> list:
        i, j = self.span(a, b)
        out = {}
        for k in range(i, j):
            t5 = int(self.t[k]) - int(self.t[k]) % 300
            if t5 not in out:
                out[t5] = [t5, self.o[k], self.h[k], self.l[k], self.c[k]]
            else:
                c = out[t5]
                c[2], c[3], c[4] = max(c[2], self.h[k]), min(c[3], self.l[k]), self.c[k]
        return [tuple(v) for _, v in sorted(out.items())]


def lit_journal(root: str = ROOT) -> dict:
    return {int(r["entry_t"]): r for r in read_jsonl(os.path.join(root, "data", "lit_journal.jsonl"))
            if r.get("entry_t") is not None and r.get("source") in ("pc", "live", "sim")}


def vix_closes(root: str = ROOT) -> list:
    try:
        import pandas as pd
        v = pd.read_csv(os.path.join(root, "data", "VIX_1d.csv"))
        return list(zip(v["date"].astype(str), v["close"].astype(float)))
    except Exception:
        return []


def vix_band(day: str, vx: list):
    prev = [c for d, c in vx if d < day]
    if not prev:
        return None
    v = prev[-1]
    for a, b, lab in VIXB:
        if a <= v < b:
            return lab
    return None


# ================================================================================================ one entry
SWEPT_NAMES = {"bu": "equal highs/lows (build-up)", "asia": "Asia", "lon": "London", "ny": "New York", "pdh": "previous-day high",
               "pdl": "previous-day low", "fra": "Frankfurt"}


def _swept_text(s) -> str:
    s = str(s)
    for k, v in SWEPT_NAMES.items():
        if s.startswith(k):
            side = "high" if s.endswith("_h") else "low" if s.endswith("_l") else ""
            return f"{v} {side}".strip()
    return s


def session_of(e) -> str:
    m = e.hour * 60 + e.minute
    if m >= 18 * 60:
        return "Asia"
    if m < 8 * 60 + 30:
        return "London"
    if m < 12 * 60:
        return "NY AM"
    return "NY PM"


def build_entry(e: dict, xs: list, bars: Bars, lj: dict, vx: list) -> dict:
    t_in = int(e["entry_t"])
    t_out = max(int(x.get("exit_t") or x.get("t") or t_in) for x in xs)
    d = 1 if e.get("side") == "buy" else -1
    qty = int(_num(e.get("qty"), 0) or 0)
    px = _num(e.get("entry")) or _num(((e.get("result") or {}) if isinstance(e.get("result"), dict) else {}).get("fill_px"))
    stop, tgt = _num(e.get("stop")), _num(e.get("target"))
    usd = round(sum(_num(x.get("pnl"), 0.0) or 0.0 for x in xs), 2)
    risk_pts = abs(px - stop) if px is not None and stop is not None else None
    risk_usd = round(qty * risk_pts * PV, 2) if risk_pts else None
    r = round(usd / risk_usd, 2) if risk_usd else None
    exit_px = round(px + d * (usd / qty + COMM) / PV, 2) if (px is not None and qty) else None
    mfe = mae = None
    if px is not None and risk_pts and len(bars.t):
        i, j = bars.span(t_in, t_out + 60)
        if j > i:
            hi, lo = float(bars.h[i:j].max()), float(bars.l[i:j].min())
            mfe = round((hi - px if d > 0 else px - lo) / risk_pts, 2)
            mae = round((px - lo if d > 0 else hi - px) / risk_pts, 2)
    ei, eo = _et(t_in), _et(t_out)
    day = trading_day(t_in)
    # tags: the True Day Open = the 00:00 ET 1m open of the trade's day
    tdo = "before 00:00"
    if ei.hour < 18:
        t0 = int(dt.datetime.combine(ei.date(), dt.time(0, 0), ET).timestamp())
        o0 = bars.open_at(t0) if len(bars.t) else None
        if o0 is not None and px is not None:
            tdo = "with" if (d > 0 and px < o0) or (d < 0 and px > o0) else "against"
        else:
            tdo = None
    tags = {"session": session_of(ei), "vix": vix_band(day, vx), "tdo": tdo, "sb_hour": ei.hour in (3, 10, 14),
            "weekday": ei.strftime("%a")}
    bot = str(e.get("bot") or "zlarior")
    setup, why = [], []
    j = lj.get(t_in) if bot == "zlarior" else None
    if j:
        sw = [_swept_text(s) for s in (j.get("swept") or [])]
        if sw:
            setup.append("swept " + ", ".join(sw))
        f = j.get("f") or {}
        if f.get("depth") is not None:
            setup.append(f"sweep depth {float(f['depth']):.2f} ATR")
        if f.get("disp") is not None:
            setup.append(f"displacement {float(f['disp']):.2f} ATR")
        if f.get("idm_n"):
            setup.append(f"inducement x{int(f['idm_n'])}")
        if j.get("cause"):
            why.append(f"loss cause: {j['cause']}")
    if e.get("setup"):
        setup.append(str(e["setup"]))
    if e.get("src_member") or e.get("member"):
        setup.append(str(e.get("src_member") or e.get("member")))
    if not setup:
        setup.append("LIT: sweep of a liquidity level, then a shift back (STRATEGY.md)" if bot == "zlarior" else f"{bot}: its entry rule")
    if stop is not None and px is not None:
        why.append(f"stop {stop:.2f} = 1 tick beyond the sweep extreme ({risk_pts:.2f} pts), {qty} micros = ${risk_usd:,.0f} at risk")
    if tgt is not None and px is not None and risk_pts:
        why.append(f"target {tgt:.2f} = {abs(tgt - px) / risk_pts:.1f}R")
    ex = str((xs[-1].get("reason") or "?")).upper()
    tid = f"{day}-{ei:%H%M}-{bot}-{str(e.get('acct') or 'main')[-6:]}".replace("/", "_").replace(" ", "_").replace(".", "")
    return {"id": tid, "bot": bot, "acct": str(e.get("acct") or "main"), "mode": e.get("mode") or "?", "day": day,
            "week": f"{ei.isocalendar()[0]}-W{ei.isocalendar()[1]:02d}", "entry_et": f"{ei:%Y-%m-%d %H:%M}", "exit_et": f"{eo:%H:%M}",
            "side": "LONG" if d > 0 else "SHORT", "qty": qty, "entry": px, "stop": stop, "target": tgt, "exit_px": exit_px,
            "risk_pts": round(risk_pts, 2) if risk_pts else None, "risk_usd": risk_usd, "usd": usd, "r": r, "mfe_r": mfe, "mae_r": mae,
            "held_min": round((t_out - t_in) / 60.0, 1), "exit": ex, "setup": setup, "why": why, "tags": tags,
            "_t": (t_in, t_out, d)}


# ================================================================================================ the week
def week_summary(rows: list) -> dict:
    n = len(rows)
    usd = round(sum(x["usd"] for x in rows), 2)
    rs = [x["r"] for x in rows if x["r"] is not None]
    w = [x for x in rows if x["usd"] > 0]
    out = {"week": rows[0]["week"], "trades": n, "wins": len(w), "usd": usd, "r": round(sum(rs), 2) if rs else None,
           "best": max(rows, key=lambda x: x["usd"])["id"], "worst": min(rows, key=lambda x: x["usd"])["id"], "by": {}, "learned": []}
    for tag in ("session", "tdo", "sb_hour", "vix"):
        g = defaultdict(lambda: [0, 0.0])
        for x in rows:
            g[str(x["tags"].get(tag))][0] += 1
            g[str(x["tags"].get(tag))][1] += x["usd"]
        out["by"][tag] = {k: {"n": v[0], "usd": round(v[1], 2)} for k, v in sorted(g.items())}
    L = out["learned"]
    L.append(f"{n} trade(s), {len(w)} winner(s), {'+' if usd >= 0 else '-'}${abs(usd):,.0f}" + (f", {sum(rs):+.2f}R" if rs else "") + ".")
    gave = [x for x in rows if x["usd"] <= 0 and (x["mfe_r"] or 0) >= 1.0]
    if gave:
        L.append(f"{len(gave)} losing / flat trade(s) were +1R or more first (best +{max(x['mfe_r'] for x in gave):.1f}R) before they ended: "
                 "the breakeven / profit rules are where that money went.")
    near = [x for x in rows if x["usd"] > 0 and (x["mae_r"] or 0) >= 0.8]
    if near:
        L.append(f"{len(near)} winner(s) came within 0.2R of the stop first: the stop is tight, not loose.")
    ses = out["by"]["session"]
    if len(ses) > 1:
        b = max(ses.items(), key=lambda kv: kv[1]["usd"])
        z = min(ses.items(), key=lambda kv: kv[1]["usd"])
        L.append(f"best session {b[0]} (${b[1]['usd']:+,.0f} on {b[1]['n']}), worst {z[0]} (${z[1]['usd']:+,.0f} on {z[1]['n']}).")
    td = out["by"]["tdo"]
    if "with" in td or "against" in td:
        L.append("True Day Open side: " + ", ".join(f"{k} {v['n']} trade(s) ${v['usd']:+,.0f}" for k, v in td.items()) + ".")
    L.append("Small sample: a week is a story, not a rule (the research needs 100+ trades per pattern).")
    return out


def week_md(s: dict, rows: list) -> str:
    t = [f"# Week {s['week']}: what we learned (auto, tools/journal_build.py)", ""]
    t += [f"- {x}" for x in s["learned"]] + ["", "| Trade | bot | side | R | $ | MFE / MAE R | exit | tags |", "|---|---|---|---|---|---|---|---|"]
    for x in rows:
        tg = x["tags"]
        t.append(f"| {x['entry_et']} | {x['bot']} | {x['side']} {x['qty']} | {x['r']} | {x['usd']:+,.0f} | {x['mfe_r']} / {x['mae_r']} | {x['exit']} | "
                 f"{tg['session']}, VIX {tg['vix']}, TDO {tg['tdo']}{', SB hour' if tg['sb_hour'] else ''} |")
    return "\n".join(t) + "\n"


# ================================================================================================ main
def build(rows_file=None, bars_path=None, out_dir=OUT_DIR, week_dir=WEEK_DIR, include_paper=False, charts=True, root=ROOT) -> dict:
    rows = ledger_rows(root, rows_file)
    pairs = pair(rows, include_paper)
    bars = Bars(bars_path)
    lj, vx = lit_journal(root), vix_closes(root)
    entries = [build_entry(e, xs, bars, lj, vx) for e, xs in pairs]
    os.makedirs(out_dir, exist_ok=True)
    if charts:
        cd = os.path.join(out_dir, "charts")
        os.makedirs(cd, exist_ok=True)
        for x in entries:
            t_in, t_out, d = x["_t"]
            c5 = bars.candles5(t_in - 3600, t_out + 1800)
            png = pngchart.candle_png(c5, x["entry"], x["stop"], x["target"], x["exit_px"], t_in, t_out, d,
                                      title=f"{x['entry_et']} {x['bot']} {x['side']} {x['qty']} {x['r'] if x['r'] is not None else ''}R")
            with open(os.path.join(cd, x["id"] + ".png"), "wb") as fh:
                fh.write(png)
            x["chart"] = f"charts/{x['id']}.png"
    weeks = []
    byw = defaultdict(list)
    for x in entries:
        byw[x["week"]].append(x)
    if week_dir:
        os.makedirs(week_dir, exist_ok=True)
    for wk in sorted(byw):
        s = week_summary(byw[wk])
        weeks.append(s)
        if week_dir:
            with open(os.path.join(week_dir, f"week-{wk}.md"), "w", encoding="utf-8") as fh:
                fh.write(week_md(s, byw[wk]))
    for x in entries:
        x.pop("_t", None)
    doc = {"v": VERSION, "built": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"), "n": len(entries),
           "source": "the bot's ledger (real = live / sim accounts" + (" + paper" if include_paper else "") + ")", "trades": entries,
           "weeks": weeks}
    tmp = os.path.join(out_dir, "entries.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    os.replace(tmp, os.path.join(out_dir, "entries.json"))
    return doc


def due(now, path: str | None = None) -> bool:
    e = dt.datetime.fromtimestamp(now, ET)
    if e.weekday() >= 5 or e.hour * 60 + e.minute < RUN_FROM:
        return False
    try:
        with open(path or STATE, encoding="utf-8") as fh:
            st = json.load(fh)
    except Exception:
        st = {}
    return st.get("day") != e.date().isoformat()


def maybe_run(now=None, state_path: str | None = None, out_dir: str | None = None) -> dict | None:
    """tools/pc_report.py's hook (the PC's 15-minute task): once a weekday from 17:20 ET, after the data pipe's 17:05 pack, the
    journal of every real trade into data/journal/ (entries.json, charts/, weeks/; gitignored). Read-only, never raises."""
    import time as _time
    try:
        now = _time.time() if now is None else now
        if os.environ.get("LE_JOURNAL") == "0" or os.environ.get("LE_SELFTEST_CHILD") == "1" or not due(now, state_path):
            return None
        od = out_dir or PC_DIR
        try:
            doc = build(None, None, od, os.path.join(od, "weeks"))
            st = {"day": dt.datetime.fromtimestamp(now, ET).date().isoformat(), "t": int(now), "n": doc["n"], "weeks": len(doc["weeks"])}
        except Exception as e:
            st = {"day": dt.datetime.fromtimestamp(now, ET).date().isoformat(), "t": int(now), "n": None,
                  "error": f"{e.__class__.__name__}: {str(e)[:160]}"}
        p = state_path or STATE
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        return st
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the auto trade journal (read-only)")
    ap.add_argument("--rows", default=None)
    ap.add_argument("--bars", default=None)
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--weeks", default=WEEK_DIR)
    ap.add_argument("--all", action="store_true", help="include paper trades")
    ap.add_argument("--no-charts", action="store_true")
    a = ap.parse_args(argv)
    d = build(a.rows, a.bars, a.out, a.weeks, a.all, not a.no_charts)
    print(f"journal: {d['n']} trade(s), {len(d['weeks'])} week(s) -> {os.path.join(a.out, 'entries.json')}")
    for s in d["weeks"][-2:]:
        print(f"  {s['week']}: " + " ".join(s["learned"][:2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
