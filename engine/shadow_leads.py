"""SHADOW LEADS (2026-11-21, day-edge2): what two PAPER leads WOULD have done next to what the bot really did. OBSERVE ONLY.

It never routes, sizes, blocks or delays anything: it is not called from the trading loop at all. It runs after the session
on files the PC already writes (the data pipe's packed day, logs/datapipe/days/<day>/: bars/<ROOT>_1m|5m.csv.gz + the day's
ledger rows trades.jsonl.gz, engine/datapipe.py) and appends one JSON line per signal to data/shadow_leads.jsonl (gitignored).
Every entry point catches every exception (maybe_run never raises).

The leads (research only; neither is a live rule, both failed their pre-set bars and are watched forward):
  A3   ATLAS stop entry (research/writeups/edge2-2026-11-21.md): instead of the market order at the 5m open, a stop 12 ticks
       past that open, live 5 minutes, filled at the trigger + 2 ticks; if the trade's stop is traded first: no trade.
       Per ATLAS entry (account B "acctb*", Rapid lane "acctr*"): would-fill y/n, the fill minute and price from the PC's 1m bars,
       then both the shadow and the bot's own entry (its fill price when the ledger has one, else open + 1 tick) are walked on
       the same 1m bars to the same stop / target / 15:55 flat: R in units of the bot's own risk. delta = shadow R - model R.
  ES   Zlarior on MES when ES's planned reward per risk is >= 1.25 x NQ's (litedge es_room, research/writeups/
       lit-edge-2026-11-20.md; rule of tools/lit_more_money.es_trade_for): per Zlarior entry (main account), ES's own sweep
       window (from the NQ sweep-extreme bar = the bar 1 tick inside the NQ stop), ES stop 1 tick beyond ES's extreme there,
       ES VIX band target (ES 18:00 open +- vix_k x prior VIX close / 100 / sqrt(252) x that open), >= 1.5R, <= 8R, managed
       on ES 5m (stop first, target, BE at +1R -> entry + 0.75, flat 15:55). switch = ES R:R >= 1.25 x NQ's planned R:R;
       es_R (ES result in ES R) vs nq_R (the bot's booked NQ result in NQ R, from the exit row's $).

Off switch: data/shadow_leads.json {"on": false} (missing file = on). Output rows are de-duplicated by (lead, src, entry_t).

    python -X utf8 -m engine.shadow_leads --day 2026-11-20      # one packed day
    python -X utf8 -m engine.shadow_leads --summary [--days 7]  # the weekly line ("A3 shadow: n signals, +x R vs live")
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import math
import os
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "data", "shadow_leads.json")
OUT = os.path.join(ROOT, "data", "shadow_leads.jsonl")
DAYS_DIR = os.path.join(ROOT, "logs", "datapipe", "days")
VIX_CSV = os.path.join(ROOT, "data", "VIX_1d.csv")
ET = ZoneInfo("America/New_York")
TICK = 0.25
A3_TICKS, A3_MIN, A3_ADD = 12, 5, 2
ES_K, ES_STOP, ES_BEO, ES_MIN_R, ES_MAX_R, ES_SWITCH = 0.28, (2.25, 22.5), 0.75, 1.5, 8.0, 1.25
FLAT_MOD = 955


# ================================================================================================ small helpers
def is_on(path: str | None = None) -> bool:
    try:
        with open(path or CFG, encoding="utf-8") as fh:
            return json.load(fh).get("on", True) is not False
    except FileNotFoundError:
        return True
    except Exception:
        return True


def _mod(t) -> int:
    e = dt.datetime.fromtimestamp(int(t), ET)
    return e.hour * 60 + e.minute


def _num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _bars(data: bytes | None) -> list:
    """[(t, o, h, l, c)] from a pcbars gzip CSV (time = bar open, unix s)."""
    if not data:
        return []
    try:
        raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    except Exception:
        return []
    out = []
    for i, ln in enumerate(raw.decode("ascii", "replace").splitlines()):
        p = ln.split(",")
        if i == 0 or len(p) < 5:
            continue
        try:
            out.append((int(float(p[0])), float(p[1]), float(p[2]), float(p[3]), float(p[4])))
        except ValueError:
            continue
    return sorted(out)


def load_day(day: str, days_dir: str | None = None) -> dict:
    """{"bars": {"NQ_1m": [...], "NQ_5m": [...], "ES_5m": [...]}, "rows": [...]} from a packed day folder."""
    d = os.path.join(days_dir or DAYS_DIR, day)
    out = {"bars": {}, "rows": []}

    def rd(rel):
        try:
            with open(os.path.join(d, rel), "rb") as fh:
                return fh.read()
        except OSError:
            return None
    for key, roots in (("NQ", ("NQ", "MNQ")), ("ES", ("ES", "MES"))):
        for tf in ("1m", "5m"):
            for r in roots:
                b = _bars(rd(f"bars/{r}_{tf}.csv.gz"))
                if b:
                    out["bars"][f"{key}_{tf}"] = b
                    break
    raw = rd("trades.jsonl.gz")
    if raw:
        try:
            txt = gzip.decompress(raw).decode("utf-8", "replace") if raw[:2] == b"\x1f\x8b" else raw.decode("utf-8", "replace")
            out["rows"] = [json.loads(x) for x in txt.splitlines() if x.strip()]
        except Exception:
            out["rows"] = []
    return out


def _entries(rows, pred):
    """(entry row, exit row | None) per entry_t of the rows that match pred (side buy / sell)."""
    ent, ex = {}, {}
    for r in rows:
        if not isinstance(r, dict) or not pred(r) or r.get("entry_t") is None:
            continue
        try:
            et_ = int(r["entry_t"])
        except (TypeError, ValueError):
            continue
        if r.get("side") in ("buy", "sell") and (r.get("result") or {}).get("ok", True) is not False:
            ent.setdefault((str(r.get("src")), et_), r)
        elif r.get("side") == "exit":
            ex[(str(r.get("src")), et_)] = r
    return [(k, e, ex.get(k)) for k, e in sorted(ent.items(), key=lambda kv: kv[0][1])]


def _fill_px(r) -> float | None:
    res = r.get("result") if isinstance(r.get("result"), dict) else {}
    for k in ("fill_price", "avg_price", "fill_px", "price", "avg"):
        v = _num(res.get(k))
        if v:
            return v
    return None


def walk(bars, k0, d, entry, stop, tgt, first_stop_only=False, be=None):
    """Walk bars[k0:] from an entry: stop first, then the target (1 tick through), optional BE (trigger R, new stop), flat at
    the 15:55 bar. first_stop_only: the fill bar can only stop (conservative). -> (exit price, kind, k)."""
    cur, moved = stop, False
    risk = (entry - stop) * d
    for k in range(k0, len(bars)):
        t, o, h, l, c = bars[k]
        if _mod(t) >= FLAT_MOD and k > k0:
            return o, "EOD", k
        lo_d, hi_d = (l, h) if d == 1 else (-h, -l)
        if lo_d <= cur * d:
            return cur - d * TICK, ("BE" if moved else "STOP"), k
        if first_stop_only and k == k0:
            continue
        if tgt is not None and hi_d >= tgt * d + TICK:
            return tgt, "TARGET", k
        if be and not moved and hi_d >= entry * d + be[0] * risk:
            cur, moved = entry + d * be[1], True
    t, o, h, l, c = bars[-1]
    return c, "EOD", len(bars) - 1


# ================================================================================================ A3
def a3_rows(day_data: dict) -> list:
    b1 = day_data["bars"].get("NQ_1m") or []
    out = []
    if not b1:
        return out
    ts = [b[0] for b in b1]
    import bisect
    for (src, et_), e, x in _entries(day_data["rows"], lambda r: str(r.get("src", "")).startswith(("acctb", "acctr"))):
        d = 1 if e.get("side") == "buy" else -1
        stop, tgt = _num(e.get("stop")), _num(e.get("target"))
        rec = {"lead": "A3", "day": None, "src": src, "entry_t": et_, "dir": d, "strategy": e.get("strategy") or e.get("src")}
        k = bisect.bisect_left(ts, et_)
        if stop is None or k >= len(b1) or b1[k][0] - et_ > 120:
            out.append({**rec, "status": "no 1m bar / stop"})
            continue
        o = b1[k][1]
        live_e = _fill_px(e) or (o + d * TICK)
        risk = (live_e - stop) * d
        if risk <= 0:
            out.append({**rec, "status": "bad risk"})
            continue
        trig = o + d * A3_TICKS * TICK
        fill_k, why = None, "no fill (never 12 ticks in 5 min)"
        for m in range(A3_MIN):
            if k + m >= len(b1) or b1[k + m][0] >= et_ + 60 * A3_MIN:
                break
            _, _, h, l, _ = b1[k + m]
            hi_d, lo_d = (h, l) if d == 1 else (-l, -h)
            if lo_d <= stop * d:
                fill_k, why = (k + m, "filled and stopped in the same minute") if hi_d >= trig * d else (None, "avoided (stop first)")
                break
            if hi_d >= trig * d:
                fill_k, why = k + m, "filled"
                break
        px_m, kind_m, _ = walk(b1, k, d, live_e, stop, tgt)
        model_r = round((px_m - live_e) * d / risk, 3)
        rec.update(status="ok", open=o, model_entry=round(live_e, 2), stop=stop, target=tgt, risk_pts=round(risk, 2),
                   model_exit=kind_m, model_R=model_r)
        if fill_k is None:
            rec.update(would_fill=False, why=why, shadow_R=0.0)
        else:
            f = trig + d * A3_ADD * TICK
            if why.startswith("filled and stopped"):
                px_s, kind_s = stop - d * TICK, "STOP"
            else:
                px_s, kind_s, _ = walk(b1, fill_k, d, f, stop, tgt, first_stop_only=True)
            rec.update(would_fill=True, why=why, fill_min=fill_k - k, fill_px=round(f, 2), shadow_exit=kind_s,
                       shadow_R=round((px_s - f) * d / risk, 3))
        rec["delta_R"] = round(rec["shadow_R"] - model_r, 3)
        if x is not None and _num(x.get("pnl")) is not None:
            rec["booked_usd"] = round(float(x["pnl"]), 2)
        out.append(rec)
    return out


# ================================================================================================ ES (litedge es_room)
def _vix_prev(day: str, path: str | None = None) -> float | None:
    try:
        best = None
        with open(path or VIX_CSV, encoding="utf-8") as fh:
            for ln in fh:
                p = ln.strip().split(",")
                if len(p) >= 5 and p[0][:4].isdigit() and p[0] < day:
                    best = _num(p[4]) or best
        return best
    except OSError:
        return None


def _vix_k() -> float:
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        for blk in (m, m.get("lit") or {}, m.get("params") or {}):
            if isinstance(blk, dict) and _num(blk.get("vix_k")):
                return float(blk["vix_k"])
    except Exception:
        pass
    return 1.0


def es_rows(day_data: dict, day: str, vix: float | None = None, vix_k: float | None = None) -> list:
    n5, e5 = day_data["bars"].get("NQ_5m") or [], day_data["bars"].get("ES_5m") or []
    out = []
    if not n5:
        return out
    import bisect
    nts, ets = [b[0] for b in n5], [b[0] for b in e5]
    vix = vix if vix is not None else _vix_prev(day)
    k_v = vix_k if vix_k is not None else _vix_k()
    for (src, et_), e, x in _entries(day_data["rows"], lambda r: str(r.get("src", "")) == "main"):
        d = 1 if e.get("side") == "buy" else -1
        stop, tgt, ent = _num(e.get("stop")), _num(e.get("target")), _num(e.get("entry"))
        rec = {"lead": "ES", "day": None, "src": src, "entry_t": et_, "dir": d}
        if None in (stop, tgt, ent) or (ent - stop) * d <= 0:
            out.append({**rec, "status": "no stop / target"})
            continue
        nq_rr = round((tgt - ent) * d / ((ent - stop) * d), 3)
        rec["nq_rr"] = nq_rr
        if x is not None and _num(x.get("pnl")) is not None and _num(e.get("qty")):
            rec["nq_R"] = round(float(x["pnl"]) / (float(e["qty"]) * ((ent - stop) * d) * 2.0), 3)
        a_n = bisect.bisect_left(nts, et_)
        sw = None
        for j in range(min(a_n, len(n5)) - 1, max(-1, a_n - 145), -1):    # the NQ sweep-extreme bar (stop = 1 tick beyond it)
            ext = n5[j][3] if d == 1 else n5[j][2]
            if abs(ext - (stop + d * TICK)) <= TICK + 1e-9:
                sw = n5[j][0]
                break
        a = bisect.bisect_left(ets, et_)
        if sw is None:
            out.append({**rec, "status": "no NQ sweep bar"})
            continue
        if not e5 or a >= len(e5) or e5[a][0] - et_ > 600:
            out.append({**rec, "status": "no ES bar"})
            continue
        p = bisect.bisect_left(ets, sw)
        if a - p < 1:
            out.append({**rec, "status": "no ES sweep window"})
            continue
        es_e = e5[a][1] + d * TICK
        es_stop = (min(b[3] for b in e5[p:a]) - TICK) if d == 1 else (max(b[2] for b in e5[p:a]) + TICK)
        risk = (es_e - es_stop) * d
        if not (ES_STOP[0] <= risk <= ES_STOP[1]):
            out.append({**rec, "status": "ES stop out of range", "es_risk": round(risk, 2)})
            continue
        lo18 = int(dt.datetime.combine(dt.date.fromisoformat(day) - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp())
        o18 = next((b[1] for b in e5 if b[0] >= lo18), None)
        if not vix or not o18:
            out.append({**rec, "status": "no VIX / ES 18:00 open"})
            continue
        band = o18 + d * k_v * vix / 100.0 / math.sqrt(252.0) * o18
        if (band - es_e) * d < ES_MIN_R * risk:
            out.append({**rec, "status": "ES target under 1.5R"})
            continue
        tg = band if (band - es_e) * d <= ES_MAX_R * risk else es_e + d * ES_MAX_R * risk
        es_rr = round((tg - es_e) * d / risk, 3)
        sw_on = es_rr >= ES_SWITCH * nq_rr
        rec.update(status="ok", es_rr=es_rr, switch=bool(sw_on), es_entry=round(es_e, 2), es_stop=round(es_stop, 2), es_target=round(tg, 2))
        if sw_on:
            px, kind, _ = walk(e5, a, d, es_e, es_stop, tg, be=(1.0, ES_BEO))
            rec.update(es_exit=kind, es_R=round((px - es_e) * d / risk, 3))
            if rec.get("nq_R") is not None:
                rec["delta_R"] = round(rec["es_R"] - rec["nq_R"], 3)
        out.append(rec)
    return out


# ================================================================================================ run / store / summary
def _done(path) -> set:
    s = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                    s.add((r.get("lead"), r.get("src"), r.get("entry_t")))
                except ValueError:
                    continue
    except OSError:
        pass
    return s


def run_day(day: str, days_dir: str | None = None, out: str | None = None, cfg: str | None = None, vix=None, vix_k=None) -> dict:
    """Shadow one packed day; append the new rows. -> {"day", "added", "rows"} (never raises)."""
    try:
        if not is_on(cfg):
            return {"day": day, "off": True, "added": 0, "rows": []}
        dd = load_day(day, days_dir)
        rows = [{**r, "day": day} for r in a3_rows(dd) + es_rows(dd, day, vix=vix, vix_k=vix_k)]
        path = out or OUT
        have = _done(path)
        new = [r for r in rows if (r["lead"], r["src"], r["entry_t"]) not in have]
        if new:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                for r in new:
                    fh.write(json.dumps(r, default=float) + "\n")
        return {"day": day, "added": len(new), "rows": rows}
    except Exception as e:
        return {"day": day, "error": f"{e.__class__.__name__}: {e}", "added": 0, "rows": []}


def summary(days: int = 7, now=None, out: str | None = None) -> dict:
    """The weekly line for the board / Jarvis. A3: signals, would-fill, sum of shadow R vs the bot's own entry on the same bars.
    ES: Zlarior signals, switches, ES R vs the booked NQ R on the switched ones."""
    try:
        now = int(now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp())
        lo = (dt.datetime.fromtimestamp(now, ET).date() - dt.timedelta(days=days)).isoformat()
        R = []
        try:
            with open(out or OUT, encoding="utf-8") as fh:
                for ln in fh:
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if str(r.get("day") or "") >= lo and r.get("status") == "ok":
                        R.append(r)
        except OSError:
            pass
        a = [r for r in R if r["lead"] == "A3"]
        es = [r for r in R if r["lead"] == "ES"]
        esw = [r for r in es if r.get("switch") and r.get("delta_R") is not None]
        A = {"n": len(a), "would_fill": sum(1 for r in a if r.get("would_fill")), "shadow_R": round(sum(r["shadow_R"] for r in a), 2),
             "model_R": round(sum(r["model_R"] for r in a), 2), "delta_R": round(sum(r["delta_R"] for r in a), 2)}
        E = {"n": len(es), "switch": sum(1 for r in es if r.get("switch")), "delta_R": round(sum(r["delta_R"] for r in esw), 2),
             "es_R": round(sum(r["es_R"] for r in esw), 2), "nq_R": round(sum(r["nq_R"] for r in esw), 2)}
        line = (f"A3 shadow: {A['n']} signals, {A['would_fill']} would fill, {A['delta_R']:+.1f}R vs live | "
                f"ES shadow: {E['switch']} of {E['n']} Zlarior trades would be MES, {E['delta_R']:+.1f}R vs live (last {days} days)")
        return {"since": lo, "A3": A, "ES": E, "line": line}
    except Exception as e:
        return {"error": f"{e.__class__.__name__}: {e}", "line": "shadow leads: no summary"}


def maybe_run(now=None, days_dir: str | None = None, out: str | None = None, say=None) -> int:
    """For the PC's nightly job (after engine/datapipe packed the day): shadow every packed day not shadowed yet (last 10).
    Returns the rows added. Never raises."""
    try:
        if not is_on():
            return 0
        dd = days_dir or DAYS_DIR
        try:
            names = sorted(n for n in os.listdir(dd) if len(n) == 10 and n[4] == "-")[-10:]
        except OSError:
            return 0
        done_days = set()
        try:
            with open(out or OUT, encoding="utf-8") as fh:
                for ln in fh:
                    try:
                        done_days.add(json.loads(ln).get("day"))
                    except ValueError:
                        continue
        except OSError:
            pass
        n = 0
        for day in names:
            if day in done_days and day != names[-1]:
                continue
            n += int(run_day(day, dd, out).get("added") or 0)
        if say and n:
            say(f"shadow leads: {n} new rows; " + summary(out=out)["line"])
        return n
    except Exception:
        return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args(argv)
    if a.day:
        r = run_day(a.day)
        print(json.dumps({k: v for k, v in r.items() if k != "rows"}), f"({len(r.get('rows') or [])} signals)")
    if a.summary or not a.day:
        print(summary(a.days)["line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
