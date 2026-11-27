"""Order flow CONFLUENCE forward log (night-of-conflog 2026-11-27; READ-ONLY, PAPER: it never trades, sizes, arms or routes).

One row per finished real LIT (Zlarior) / ATLAS trade with the cheap order-flow fields that let the four confluence ideas of
research/orderflow/DESIGN_confluence.md (C-a absorbed-bar entry, C-b size when absorbed, C-c hard-flip exit, C-d ATLAS
non-adverse entry) be scored on forward days (research/orderflow/confluence_results.md "LEAD_WIRES"). It only READS the day's
order-flow summary (engine/ofsum files, logs/datapipe/days/<day>/of) and the bots' ledgers, and WRITES:
  data/of_confluence_log.jsonl                         (gitignored; bounded: MAX_BYTES, oldest rows dropped)
  logs/datapipe/days/<day>/of/NQ_conflog.json.gz       (the day's rows: the data feed carries them to the cloud)
Rows carry no account name / id / balance: bot, direction, times, prices, micros, the trade's $ and market data only.

Run by the tick autopilot's nightly step (engine/tickrec.autopilot, next to oflive.journal_kick: outside trading hours, its
own low-priority process). kick() also refuses 09:25-16:10 ET on weekdays itself. Never raises. Standard library only.
The definitions are the frozen research ones (research/orderflow/of_confluence.py; tests/test_of_conflog.py checks parity).
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import statistics
import time

from . import oflive

ROOT = oflive.ROOT
TICK = 0.25
ZONE_TICKS, ABS_SHARE, MIN_TRADES = 8, 0.20, 20           # OF1 (of_battery.Day.zone / PREREG_ticks)
FLIP_SHARE, WIN_BARS = 0.25, 6                            # DESIGN_confluence.md
MAX_BARS = 80
LOG = os.path.join(ROOT, "data", "of_confluence_log.jsonl")
EXPORT_NAME = "NQ_conflog.json.gz"
MAX_BYTES = 3_000_000
KEEP_ROWS = 3000
V = 1
ET = oflive.ET


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET) if ET else dt.datetime.utcfromtimestamp(int(t))


def _day(t) -> str:
    return _et(t).strftime("%Y-%m-%d")


def quiet(now: float) -> bool:
    """True outside 09:25-16:10 ET on weekdays (the bot's busy window: never run then)."""
    e = _et(now)
    return e.weekday() >= 5 or not (9 * 60 + 25 <= e.hour * 60 + e.minute <= 16 * 60 + 10)


# ------------------------------------------------------------------------------------------------ the frozen reads
def zone_absorbed(S: dict, j: int, d: int):
    """OF1 at bar j (index into S["bars"]): None (bar < 20 trades / no footprint) or True / False."""
    b = S["bars"][j]
    if int(b.get("n") or 0) < MIN_TRADES:
        return None
    cells = S["_fp"].get(j)
    if not cells:
        return None
    kmax = int(round((b["h"] - b["l"]) / TICK))
    z = [f for f in cells if (f["k"] <= ZONE_TICKS if d == 1 else f["k"] >= kmax - ZONE_TICKS)]
    vz = sum(f["a"] + f["b"] + f["u"] for f in z)
    dz = sum(f["a"] - f["b"] for f in z)
    return bool(vz > 0 and dz * d < 0 and abs(dz) >= ABS_SHARE * vz)


def _delta(b):
    return float(b.get("buy") or 0) - float(b.get("sell") or 0)


def _med_rth_before(S, j):
    v = [float(b.get("vol") or 0) for b in S["bars"][:j] if 570 <= oflive._mod(b["t"]) < 960]
    return statistics.median(v) if v else 0.0


def flip_info(S, j, d, entry):
    """(share, vol_x_med, close_wrong_side, hard) of bar j: share = |delta| / volume when delta is AGAINST the trade, else 0."""
    b = S["bars"][j]
    vol = float(b.get("vol") or 0)
    dl = _delta(b)
    against = dl * d < 0 and vol > 0
    share = abs(dl) / vol if against else 0.0
    med = _med_rth_before(S, j)
    vxm = vol / med if med > 0 else None
    wrong = b["c"] * d < entry * d
    hard = bool(against and share >= FLIP_SHARE and vol >= med and wrong)
    return round(share, 3), (round(vxm, 2) if vxm is not None else None), bool(wrong), hard


def _prep(S):
    if "_fp" not in S:
        fp = {}
        for f in S["fp"]:
            fp.setdefault(int(f["bar"]), []).append(f)
        S["_fp"] = fp
    return S


def fields(S: dict, tr: dict) -> dict:
    """The forward fields of one trade tr = {"bot", "d", "t" (entry), "x" (exit time or None), "entry", "stop", ...}."""
    S = _prep(S)
    bars, d, te = S["bars"], int(tr["d"]), int(tr["t"])         # te = the ledger's entry_t (the setup bar: the journal's key)
    tf = int(tr.get("tf") or te)                                   # tf = when the entry was routed (~ the fill)
    tx = int(tr.get("x") or tf + 6 * 3600)
    out = {}
    # C-b: the sweep extreme bar (6 bars before entry), oflive.said_at = the journal's read (kept identical)
    s = oflive.said_at({"bars": bars, "fp": S["fp"]}, te, d, tr.get("stop") or 0)
    out.update(sweep_read=s.get("read"), sweep_vz=s.get("vz"), sweep_dz=s.get("dz"))
    idx = [i for i, b in enumerate(bars) if te - 1800 <= b["t"] < te]
    if idx:
        j = min(idx, key=lambda i: bars[i]["l"]) if d == 1 else max(idx, key=lambda i: bars[i]["h"])
        out["sweep_abs_bar"] = zone_absorbed(S, j, d)
    # bars closing after the fill (a bar "closes" at t + 300)
    aft = [i for i, b in enumerate(bars) if b["t"] + 300 > tf]
    # C-a: the first absorbed closed bar within WIN_BARS after the fill (+ the next 5m open; the cloud takes the 1m open)
    out["abs1_t"] = out["abs1_open5"] = None
    for i in aft[:WIN_BARS]:
        if zone_absorbed(S, i, d):
            out["abs1_t"] = int(bars[i]["t"]) + 300
            out["abs1_open5"] = bars[i + 1]["o"] if i + 1 < len(bars) else None
            break
    # C-c: the first bar (fill -> exit) with delta against; its share / volume vs median / hard flag, + the first HARD one
    out["flip1_t"] = out["flip1_share"] = out["flip1_vol_x_med"] = out["hard1_t"] = None
    for i in aft:
        if bars[i]["t"] + 300 > tx:
            break
        sh, vxm, wrong, hard = flip_info(S, i, d, float(tr["entry"]))
        if sh > 0 and out["flip1_t"] is None:
            out.update(flip1_t=int(bars[i]["t"]) + 300, flip1_share=sh, flip1_vol_x_med=vxm)
        if hard:
            out["hard1_t"] = int(bars[i]["t"]) + 300
            break
    # C-d (ATLAS): the signal bar = the last bar closing at / before the entry; the first non-adverse closed bar from it
    sig = [i for i, b in enumerate(bars) if b["t"] + 300 <= tf]
    out["sig_delta"] = out["sig_vol"] = out["nonadv1_t"] = out["nonadv1_open5"] = None
    if sig:
        j = sig[-1]
        out["sig_delta"], out["sig_vol"] = int(_delta(bars[j])), int(bars[j].get("vol") or 0)
        for i in range(j, min(len(bars), j + WIN_BARS + 1)):
            if _delta(bars[i]) * d >= 0:
                out["nonadv1_t"] = int(bars[i]["t"]) + 300
                out["nonadv1_open5"] = bars[i + 1]["o"] if i + 1 < len(bars) else None
                break
    # the replay series: [bar open t, delta, volume, close] from the fill's bar to the exit's bar
    ser = [[int(b["t"]), int(_delta(b)), int(b.get("vol") or 0), b["c"]] for b in bars if b["t"] + 300 > tf and b["t"] < tx + 300]
    out["bars"] = ser[:MAX_BARS]
    return out


# ------------------------------------------------------------------------------------------------ trades of a day
def _ledgers(root):
    """(bot, row) for every ledger row: data/live_state*.json + the data pipe's archive (de-duplicated later)."""
    out = []
    try:
        names = sorted(os.listdir(os.path.join(root, "data")))
    except OSError:
        names = []
    for n in names:
        if not (n.startswith("live_state") and n.endswith(".json")) or ".corrupt" in n or n.endswith(".tmp.json"):
            continue
        stem = n[:-5][len("live_state"):].lstrip("_")
        bot = "lit" if not stem else ("atlas" if stem.startswith("acctb") else None)
        if bot is None:
            continue
        st = oflive._read_json(os.path.join(root, "data", n), {}) or {}
        for r in (st.get("ledger") or []) if isinstance(st, dict) else []:
            if isinstance(r, dict):
                out.append((bot, r))
    for r in oflive._jl(os.path.join(root, "logs", "datapipe", "ledger_archive.jsonl")):
        b = r.get("bot")
        bot = "lit" if b in (None, "zlarior") and str(r.get("src") or "main") == "main" else ("atlas" if b == "atlas" else None)
        if bot and str(r.get("src") or "").startswith("accounts/"):
            bot = None
        if bot:
            out.append((bot, r))
    return out


def _fill_px(res):
    if not isinstance(res, dict):
        return None
    for k in ("fill_px", "avg_px", "avg_fill", "fill", "price"):
        v = res.get(k)
        try:
            if v is not None and float(v) > 0:
                return float(v)
        except (TypeError, ValueError):
            pass
    return None


def trades_of(day: str, root: str = ROOT) -> list:
    """Finished real trades of one ET day: [{"bot", "d", "t" (entry_t), "tf" (routed), "x", "entry" (signal), "fill", "stop", "target", "qty",
    "pnl", "exit_kind", "paper"}]. A trade is finished when it has an exit row with a $."""
    ent, ex = {}, {}
    for bot, r in _ledgers(root):
        try:
            et_ = int(r.get("entry_t") or 0)
        except (TypeError, ValueError):
            continue
        if not et_ or _day(et_) != day:
            continue
        k = (bot, et_)
        side = r.get("side")
        if side in ("buy", "sell") and (r.get("result") or {}).get("ok", True) and r.get("stop"):
            ent.setdefault(k, {"bot": bot, "d": 1 if side == "buy" else -1, "t": et_, "tf": int(r.get("t") or et_),
                               "entry": float(r.get("entry") or 0) or None, "fill": _fill_px(r.get("result")),
                               "stop": float(r["stop"]), "target": float(r["target"]) if r.get("target") else None,
                               "qty": int(r.get("qty") or 0), "paper": str((r.get("result") or {}).get("adapter") or "").lower() in ("", "paper")})
        elif side == "exit" and r.get("pnl") is not None:
            x = ex.setdefault(k, {"pnl": {}, "x": 0, "kind": None})
            x["pnl"][int(r.get("t") or 0)] = float(r["pnl"])
            x["x"] = max(x["x"], int(r.get("t") or 0)); x["kind"] = r.get("reason") or x["kind"]
    out = []
    for k, e in sorted(ent.items(), key=lambda kv: kv[0][1]):
        if k not in ex:
            continue
        x = ex[k]
        e = {**e, "x": x["x"] or None, "pnl": round(sum(x["pnl"].values()), 2), "exit_kind": x["kind"]}
        if e["entry"] and e["fill"]:
            e["slip_ticks"] = round((e["fill"] - e["entry"]) * e["d"] / TICK, 1)
        out.append(e)
    return out


# ------------------------------------------------------------------------------------------------ the nightly kick
def day_rows(day: str, root: str = ROOT) -> list | None:
    S = oflive._summary(day, root)
    if S is None:
        return None
    rows = []
    for tr in trades_of(day, root):
        if tr.get("entry") is None:
            continue
        try:
            rows.append({"v": V, "day": day, **tr, **fields(S, tr)})
        except Exception as e:  # noqa: BLE001
            rows.append({"v": V, "day": day, **tr, "error": e.__class__.__name__})
    return rows


def _export(day, rows, root):
    try:
        d = os.path.join(root, "logs", "datapipe", "days", day, "of")
        os.makedirs(d, exist_ok=True)
        raw = json.dumps({"v": V, "paper_research": True, "day": day, "rows": rows}, separators=(",", ":"), default=float).encode()
        if len(raw) > 150_000:                      # the day bundle's 200 KB per-file cap: drop the series first
            raw = json.dumps({"v": V, "paper_research": True, "day": day, "rows": [{**r, "bars": []} for r in rows]},
                             separators=(",", ":"), default=float).encode()
        with gzip.open(os.path.join(d, EXPORT_NAME), "wb") as fh:
            fh.write(raw)
        return True
    except Exception:  # noqa: BLE001
        return False


def _bound(path):
    try:
        if os.path.getsize(path) <= MAX_BYTES:
            return
        rows = oflive._jl(path)[-KEEP_ROWS:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":"), default=float) + "\n")
        os.replace(tmp, path)
    except Exception:  # noqa: BLE001
        pass


def kick(root: str = ROOT, now: float | None = None, days_back: int = 5, log: str | None = None) -> dict:
    """Append the finished ET days (last days_back with a summary, before today) not logged yet. Never raises."""
    try:
        now = now or time.time()
        if os.environ.get("LE_OFCONFLOG") == "0":
            return {"ran": False, "why": "off"}
        if not quiet(now):
            return {"ran": False, "why": "trading hours"}
        lp = log or LOG
        have = {r.get("day") for r in oflive._jl(lp) if r.get("day_done")}
        today = _day(now)
        base = os.path.join(root, "logs", "datapipe", "days")
        try:
            cands = sorted(d for d in os.listdir(base) if len(d) == 10 and d < today)[-days_back:]
        except OSError:
            cands = []
        added, n = [], 0
        for d in cands:
            if d in have:
                continue
            rows = day_rows(d, root)
            if rows is None:
                continue
            _export(d, rows, root)
            os.makedirs(os.path.dirname(lp), exist_ok=True)
            with open(lp, "a", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, separators=(",", ":"), default=float) + "\n")
                fh.write(json.dumps({"v": V, "day": d, "day_done": True, "n": len(rows)}) + "\n")
            added.append(d); n += len(rows)
        _bound(lp)
        return {"ran": True, "days": added, "rows": n}
    except Exception as e:  # noqa: BLE001
        return {"ran": False, "error": f"{e.__class__.__name__}: {str(e)[:80]}"}
