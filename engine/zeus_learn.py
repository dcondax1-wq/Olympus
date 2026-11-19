"""ZEUS LEARNED (night-learnloop 2026-11-19; owner: "our bot that is constantly learning both / all of our strategies, more
features, more data pulls, smarter and faster thinking bot. Anything that can help it.").

ONE nightly scorecard per strategy, on the PC after the 17:00 ET close, inside the data pipe's nightly child (engine/datapipe.run,
right after the ZEUS daily review: same day folders, same low priority, never during the session). docs/LEARN_LOOP.md
"ZEUS learned". The same pure build() runs in the cloud on the pulled day folders (tools/learn_night.py).

Per strategy (Zlarior = LIT, ATLAS, BLITZ paper, K8 Kalshi clock bets once its ledger data/kalshi_live/clock_*.json exists):
  today      trades (one per signal; $ = every live account, else paper) and $
  twin       live vs the backtest twin: Zlarior = engine/fill_audit's nightly rows (via engine/zeus_review.twin_block),
             ATLAS = engine/circuit_breaker's live-vs-twin pairs; K8 = live bets vs the paper record of the same window
  roll       rolling edge health over the last 20 / 40 / 60 trades: n, win %, PF, avg R, $; the edge light (tools/edge_pc's daily
             result data/edge/tiny.json, else research/lab/edge_health.json) for Zlarior / ATLAS, its own numbers for BLITZ / K8
  anatomy    the newest trades' path on the PC's own 1-minute bars: did the losers ever go +0.5R first (worked, then turned) or
             never; the winners' share and how much of their best move they kept (the cause words of tools/win_loss_anatomy)
  fills      entry slippage in ticks (NinjaTrader fills vs the planned entry), the twin's slippage $; K8: the average price paid
  regime     the day's tag: VIX band (prior close) + the RTH range vs its 20-session median (calm / normal / wild); the last 40
             trades split by it ("slipping in calm markets" when calm days lose and the rest win)
Adaptations: NONE automatic here. The only automatic, owner-approved responses stay where they are (engine/circuit_breaker's
SIZE DOWN / PAUSE advice push, the edge light, the ATLAS zombie-eval rule): this reports them, it never sizes, pauses, arms or
edits a setting (live_model*.json untouched); K8's weekly re-test (engine/kalshi_adapt.py, only ever smaller: half size / OFF / a
lower max price) is REPORTED here ("auto: ...") with its restore asks. Anything new becomes a Decide-card PROPOSAL ("let Claude test X?"), checked
against docs/TESTED_AND_REJECTED.md + the ZEUS Lab's rejected_forever first; the cloud (tools/learn_night.py) puts it on
tools/web_public/business/decisions.json. Never a silent change.

Outputs (logs/ is gitignored): logs/learn/YYYY-MM-DD.json (everything) + latest.json, tiny.json (<= TINY_MAX bytes: the PC
status ext key "zl" -> the ZEUS page card), proposals.jsonl, sent.json; the day folder's learn.json (the public cut: hidden bots
left out, scrubbed) rides the data feed to the cloud. ONE phone push a night ("ZEUS learned: ..."), on the private topic, type
daily_summary (notify_settings.json), LE_LEARNED_PUSH=0 = no push, LE_LEARNED=0 = off. Never raises into its caller.

    python -X utf8 -m engine.zeus_learn                 # tonight's scorecard from the local day folders (prints, sends nothing)
    python -X utf8 -m engine.zeus_learn --day 2026-11-19 --json
Tests: python -X utf8 -m tests.test_learn_night
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "logs", "learn")
VERSION = 1
STRATS = ("zlarior", "atlas", "blitz", "k8")
NAMES = {"zlarior": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ", "k8": "K8"}
WINDOWS = (20, 40, 60)
TURN_R = 0.5                   # a loser that was up this much first "worked, then turned" (tools/win_loss_anatomy.cause_of)
PV = 2.0                       # MNQ $ a point a micro (engine/circuit_breaker.PV)
TICK = 0.25
SLIP_PROPOSE = 1.5             # ticks, median entry slippage of the last >= SLIP_MIN fills -> "re-run the gates with real costs?"
SLIP_MIN = 8
EDGE_N = 20                    # trades before a rolling PF < 1 can become a proposal
REGIME_MIN = 8                 # trades in one regime before a split is named
TINY_MAX = 220
LINE_MAX = 600
K8_KILL_RATE, K8_HELD_OUT_RATE, K8_KILL_PRICE = 0.58, 0.68, 0.58   # research/lab/kalshi_candidates/K8.json + engine/kalshi_clock
LIGHT = {"G": "GREEN", "A": "AMBER", "R": "RED", "GREEN": "GREEN", "AMBER": "AMBER", "RED": "RED"}
BOT_OF = {"zlarior": "zlarior", "atlas": "atlas", "blitz": "blitz"}      # engine/datapipe ledger "bot" -> strategy


def _f(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def usd(v) -> str:
    v = round(float(v or 0))
    return "$0" if v == 0 else f"{'+' if v > 0 else '-'}${abs(v):,.0f}"


def _md(day) -> str:
    try:
        d = dt.date.fromisoformat(str(day))
        return f"{d:%b} {d.day}"
    except Exception:
        return str(day)


def _med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, default=str, separators=None if indent else (",", ":"))
    try:
        from .fsutil import replace as _rep         # retried on a Windows / OneDrive lock
        _rep(tmp, path)
    except Exception:
        os.replace(tmp, path)


def _bytes(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


# ================================================================================================ inputs (files, never the network)
def read_bars(day_dir: str) -> list:
    """The day folder's NQ (else MNQ) 1-minute bars, else 5-minute: [(t, o, h, l, c)] sorted (t = bar open, unix s), and the
    bar seconds. Stdlib only (engine/pcbars.encode's gzipped CSV)."""
    for tf, secs in (("1m", 60), ("5m", 300)):
        for root in ("NQ", "MNQ"):
            p = os.path.join(day_dir, "bars", f"{root}_{tf}.csv.gz")
            try:
                with open(p, "rb") as fh:
                    raw = fh.read()
                text = (gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw).decode("ascii", "replace")
            except (OSError, EOFError, ValueError):
                continue
            out = []
            for row in csv.reader(io.StringIO(text)):
                if not row or row[0] == "time":
                    continue
                try:
                    out.append((int(float(row[0])), float(row[1]), float(row[2]), float(row[3]), float(row[4])))
                except (ValueError, IndexError):
                    continue
            if out:
                out.sort()
                return [out, secs]
    return [[], 60]


def rth_range(bars: list):
    """(range points, range % of the last RTH close) of 09:30-16:00 ET, or (None, None)."""
    hi = lo = last = None
    for t, _o, h, l, c in bars:
        e = _et(t)
        m = e.hour * 60 + e.minute
        if 570 <= m < 960:
            hi = h if hi is None else max(hi, h)
            lo = l if lo is None else min(lo, l)
            last = c
    if hi is None or not last:
        return None, None
    return round(hi - lo, 2), round(100.0 * (hi - lo) / last, 3)


def vix_closes(root: str = ROOT) -> dict:
    """{date: VIX close} from data/VIX_1d.csv + the edge run's CBOE cache (research/runs/_cache/edge/VIX_History.csv)."""
    out = {}
    try:
        with open(os.path.join(root, "data", "VIX_1d.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                v = _f(r.get("close"))
                if r.get("date") and v is not None:
                    out[r["date"]] = v
    except OSError:
        pass
    try:
        with open(os.path.join(root, "research", "runs", "_cache", "edge", "VIX_History.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r = {str(k).lower(): v for k, v in r.items()}
                try:
                    d = dt.datetime.strptime(str(r.get("date")), "%m/%d/%Y").date().isoformat()
                except ValueError:
                    continue
                v = _f(r.get("close"))
                if v is not None and d not in out:
                    out[d] = v
    except OSError:
        pass
    return out


def prior_vix(vix: dict, day: str):
    """(date, close) of the newest VIX close before `day` (the prior close: known at the open), or (None, None)."""
    ds = [d for d in vix if d < day]
    if not ds:
        return None, None
    d = max(ds)
    return d, vix[d]


def vix_band(v) -> str | None:
    """tools/win_loss_anatomy.vix_band (the same four bands)."""
    v = _f(v)
    if v is None:
        return None
    return "VIX <15" if v < 15 else "VIX 15-20" if v < 20 else "VIX 20-25" if v < 25 else "VIX 25+"


def edge_lights(root: str = ROOT, now=None) -> dict:
    """{"zlarior": (light, src, data_to), "atlas": ...} from the PC's daily edge result (tools/edge_pc.read_tiny), else the cloud's
    research/lab/edge_health.json card."""
    out = {}
    try:
        from tools import edge_pc
        t = edge_pc.read_tiny(os.path.join(root, "data", "edge", "tiny.json"), now=now)
    except Exception:
        t = None
    if isinstance(t, dict):
        z, a = t.get("z") or [], t.get("a") or []
        if z and LIGHT.get(z[0]):
            out["zlarior"] = (LIGHT[z[0]], "edge health (PC, daily)", t.get("d"))
        if a and LIGHT.get(a[0]):
            out["atlas"] = (LIGHT[a[0]], "edge health (PC, daily)", a[3] if len(a) > 3 else t.get("d"))
    card = (_read_json(os.path.join(root, "research", "lab", "edge_health.json"), {}) or {}).get("card") or {}
    if "zlarior" not in out and LIGHT.get(card.get("light")):
        out["zlarior"] = (LIGHT[card["light"]], "edge health (cloud)", card.get("data_to"))
    ca = card.get("atlas") or {}
    if "atlas" not in out and LIGHT.get(ca.get("light")):
        out["atlas"] = (LIGHT[ca["light"]], "edge health (cloud)", ca.get("data_to"))
    return out


def breaker(root: str = ROOT) -> dict:
    """engine/circuit_breaker.status (read-only, writes nothing): {bot: {"v": verdict, "pairs": [...]}}; {} on any error."""
    try:
        from . import circuit_breaker
        if os.environ.get("LE_BREAKER", "1").strip() == "0":
            return {}
        return circuit_breaker.status(root)
    except Exception:
        return {}


def k8_rows(root: str = ROOT) -> dict:
    """{"paper": [...], "live": [...]} of engine/kalshi_clock's ledgers (data/kalshi_live/clock_paper.json / clock_live.json);
    {} while neither exists (K8 not on this PC yet)."""
    out = {}
    for k in ("paper", "live"):
        d = _read_json(os.path.join(root, "data", "kalshi_live", f"clock_{k}.json"), None)
        if isinstance(d, dict) and isinstance(d.get("rows"), list):
            out[k] = [r for r in d["rows"] if isinstance(r, dict)]
    ad = _read_json(os.path.join(root, "data", "kalshi_live", "clock_adapt.json"), None)    # engine/kalshi_adapt's weekly re-test
    if out and isinstance(ad, dict):
        out["adapt"] = ad
    return out


def hidden(root: str = ROOT) -> set:
    try:
        from . import hidden_bots
        return {str(x) for x in (hidden_bots.hidden(os.path.join(root, "dashboard_view.json")) or ())}
    except Exception:
        try:
            d = _read_json(os.path.join(root, "dashboard_view.json"), {}) or {}
            return {str(x) for x in d.get("hidden_bots") or []}
        except Exception:
            return {"blitz"}


# ================================================================================================ trades (one per signal)
def _fill(row):
    res = row.get("result") if isinstance(row.get("result"), dict) else {}
    px = [(_f(lg.get("fill_px")), int(_f(lg.get("filled")) or 0)) for lg in res.get("legs") or [] if isinstance(lg, dict)]
    px = [(p, q) for p, q in px if p is not None and q > 0]
    n = sum(q for _, q in px)
    return sum(p * q for p, q in px) / n if n else None


MODE_RANK = {"live": 0, "sim": 1, "paper": 2}


def signals(days: list) -> list:
    """Closed futures trades of every day bundle (engine/datapipe.load_day), ONE per (strategy, entry_t, direction): its $ =
    the live accounts' sum (else sim, else paper), R / slippage from the primary row (the most real, then the most micros)."""
    by = {}
    for b in days:
        rows = b.get("trades") or []
        ent = {}
        for r in rows:
            if r.get("side") in ("buy", "sell") and r.get("entry_t") is not None:
                res = r.get("result") if isinstance(r.get("result"), dict) else {}
                if res.get("ok") is False:
                    continue
                ent[(r.get("src"), int(_f(r["entry_t"]) or 0))] = r
        seen = set()
        for r in rows:
            if r.get("side") != "exit" or r.get("entry_t") is None:
                continue
            if str(r.get("reason") or "").upper() in ("NO TRADE", "KILL SWITCH"):
                continue
            pnl = _f(r.get("pnl"))
            strat = BOT_OF.get(str(r.get("bot") or ""))
            if pnl is None or strat is None:
                continue
            et_ = int(_f(r["entry_t"]) or 0)
            k0 = (r.get("src"), et_, r.get("t"))
            if k0 in seen:
                continue
            seen.add(k0)
            e = ent.get((r.get("src"), et_)) or {}
            d = 1 if e.get("side") == "buy" else -1 if e.get("side") == "sell" else 0
            q = int(_f(e.get("qty")) or _f(r.get("qty")) or 0)
            px = _fill(e)
            plan = _f(e.get("entry"))
            stop = _f(e.get("stop"))
            x = {"day": b.get("day"), "strat": strat, "src": r.get("src"), "mode": r.get("mode") or "paper", "entry_t": et_,
                 "exit_t": int(_f(r.get("exit_t")) or _f(r.get("t")) or et_), "dir": d, "qty": q, "pnl": pnl, "reason": r.get("reason"),
                 "entry": px if px is not None else plan, "plan": plan, "fill": px, "stop": stop, "target": _f(e.get("target"))}
            key = (strat, et_, d)
            by.setdefault(key, []).append(x)
    out = []
    for (strat, et_, d), xs in by.items():
        best = min(MODE_RANK.get(x["mode"], 3) for x in xs)
        real = [x for x in xs if MODE_RANK.get(x["mode"], 3) == best]
        per_src = {}
        for x in real:                                   # a partial exit = several exit rows of one account: one $ per account
            per_src.setdefault(x["src"], []).append(x)
        p = max(real, key=lambda x: (x["qty"], x["fill"] is not None))
        p = {**p, "pnl": round(sum(x["pnl"] for x in per_src[p["src"]]), 2), "accounts": len(per_src)}
        risk_pts = abs(p["entry"] - p["stop"]) if p["entry"] is not None and p["stop"] is not None else None
        risk = risk_pts * PV * p["qty"] if risk_pts and p["qty"] else None
        slip = None
        if p["fill"] is not None and p["plan"] is not None and d:
            slip = round(d * (p["fill"] - p["plan"]) / TICK, 2)
        out.append({**{k: p[k] for k in ("day", "strat", "entry_t", "exit_t", "dir", "qty", "reason", "entry", "stop", "target")},
                    "mode": p["mode"], "accounts": p["accounts"], "usd": round(sum(x["pnl"] for x in real), 2),
                    "r": round(p["pnl"] / risk, 3) if risk else None, "risk_pts": round(risk_pts, 2) if risk_pts else None,
                    "slip_ticks": slip})
    return sorted(out, key=lambda x: (x["entry_t"], x["strat"]))


def path(t: dict, bars: list, secs: int = 60) -> dict:
    """MFE / MAE in R of one trade on the day's bars (from the fill bar to the exit bar; capped at the target / one tick past
    the stop like tools/win_loss_anatomy.path_facts). {} without bars, direction or stop."""
    d, e, rp = t.get("dir"), t.get("entry"), t.get("risk_pts")
    if not bars or not d or e is None or not rp:
        return {}
    t0 = int(t["entry_t"]) - int(t["entry_t"]) % secs
    t1 = int(t.get("exit_t") or t["entry_t"])
    fav = adv = None
    for bt, _o, h, l, _c in bars:
        if bt < t0:
            continue
        if bt > t1:
            break
        f_, a_ = (h - e, e - l) if d > 0 else (e - l, h - e)
        fav = f_ if fav is None else max(fav, f_)
        adv = a_ if adv is None else max(adv, a_)
    if fav is None:
        return {}
    if t.get("target") is not None:
        fav = min(fav, abs(t["target"] - e))
    adv = min(adv, rp + TICK)
    return {"mfe_r": round(max(0.0, fav) / rp, 2), "mae_r": round(max(0.0, adv) / rp, 2)}


# ================================================================================================ the pieces (pure)
def stats(T: list) -> dict:
    """n, win %, PF ($), avg R, $ of a list of trades."""
    if not T:
        return {"n": 0}
    u = [t["usd"] for t in T]
    g, lo = sum(x for x in u if x > 0), -sum(x for x in u if x <= 0)
    R = [t["r"] for t in T if t.get("r") is not None]
    return {"n": len(T), "win": round(100.0 * sum(1 for x in u if x > 0) / len(u), 1), "pf": round(g / lo, 2) if lo > 0 else None,
            "avg_r": round(sum(R) / len(R), 3) if R else None, "usd": round(sum(u), 2), "from": T[0]["day"], "to": T[-1]["day"]}


def rolling(T: list) -> dict:
    return {str(n): stats(T[-n:]) for n in WINDOWS}


def anatomy(T: list, n: int = 20) -> dict:
    """The newest n trades with a path: losers that went +TURN_R first vs never; winners' share + what they kept."""
    P = [t for t in T[-n:] if t.get("mfe_r") is not None]
    L = [t for t in P if t["usd"] < 0]
    W = [t for t in P if t["usd"] > 0]
    turned = [t for t in L if t["mfe_r"] >= TURN_R]
    kept = [t["r"] / t["mfe_r"] for t in W if t.get("r") is not None and t["mfe_r"] > 0]
    out = {"n": len(P), "losers": len(L), "turned": len(turned), "never": len(L) - len(turned), "winners": len(W),
           "win_share": round(100.0 * len(W) / len(P), 1) if P else None,
           "kept_pct": round(100.0 * _med(kept)) if kept else None,
           "loser_mfe_med": _med([t["mfe_r"] for t in L]), "winner_mfe_med": _med([t["mfe_r"] for t in W])}
    words = []
    if L:
        words.append(f"{len(turned)} of {len(L)} losers were up +{TURN_R:g}R first (worked, then turned)" if turned
                     else f"none of {len(L)} losers ever went +{TURN_R:g}R (never worked)")
    if W and out["kept_pct"] is not None:
        words.append(f"winners kept {out['kept_pct']}% of their best move")
    out["say"] = "; ".join(words)
    return out


def fills(T: list, n: int = 20) -> dict:
    S = [t["slip_ticks"] for t in T[-n:] if t.get("slip_ticks") is not None]
    return {"n": len(S), "entry_slip_med": _med(S), "worst": max(S) if S else None}


def regime_split(T: list, facts: dict, n: int = 40) -> dict:
    """The last n trades by the day's market: range class (calm / normal / wild) and VIX under 15 or not. A split is NAMED when
    one side has >= REGIME_MIN trades, loses on average (R, else $) while the rest win."""
    last = T[-n:]

    def avg(xs):
        R = [t["r"] for t in xs if t.get("r") is not None]
        if len(R) >= max(1, len(xs) // 2):
            return round(sum(R) / len(R), 3), "R"
        return (round(sum(t["usd"] for t in xs) / len(xs), 2), "$") if xs else (None, None)
    out = {"groups": {}, "slipping": []}
    tests = (("calm markets", lambda f: f.get("range") == "calm"), ("wild markets", lambda f: f.get("range") == "wild"),
             ("VIX under 15", lambda f: (_f(f.get("vix")) or 99) < 15))
    for name, fn in tests:
        a = [t for t in last if fn(facts.get(t["day"]) or {})]
        b = [t for t in last if t not in a]
        va, ua = avg(a)
        vb, _ub = avg(b)
        out["groups"][name] = {"n": len(a), "avg": va, "unit": ua, "rest_n": len(b), "rest_avg": vb,
                               "usd": round(sum(t["usd"] for t in a), 2)}
        if len(a) >= REGIME_MIN and va is not None and va < 0 and (vb is None or vb > 0):
            out["slipping"].append(name)
    return out


def day_facts(days: list, days_dir: str | None, vix: dict) -> dict:
    """{day: {"vix", "vix_band", "range_pts", "range_pct", "range"}}: the range class vs the median of the 20 sessions before."""
    out, hist = {}, []
    for b in days:
        day = b.get("day")
        bars, _s = read_bars(os.path.join(days_dir, day)) if days_dir and day else ([], 60)
        pts, pct = rth_range(bars)
        vd, vv = prior_vix(vix, day) if day else (None, None)
        med = _med(hist[-20:]) if len(hist) >= 5 else None
        cls = None
        if pct is not None and med:
            cls = "calm" if pct < 0.75 * med else "wild" if pct > 1.33 * med else "normal"
        out[day] = {"vix": vv, "vix_date": vd, "vix_band": vix_band(vv), "range_pts": pts, "range_pct": pct, "range": cls,
                    "range_med20_pct": round(med, 3) if med else None}
        if pct is not None:
            hist.append(pct)
    return out


def regime_tag(f: dict) -> str:
    parts = []
    if f.get("vix_band"):
        parts.append(f"{f['vix_band']} ({f['vix']:.1f})" if _f(f.get("vix")) is not None else f["vix_band"])
    if f.get("range"):
        parts.append(f"{f['range']} range ({f['range_pts']:.0f} pts)" if f.get("range_pts") is not None else f"{f['range']} range")
    return ", ".join(parts) or "no bars / VIX for today"


# ---------------------------------------------------------------------------------------------- "tested and rejected" check
REJECT_PATTERNS = {"turned": r"\bBE\b|break[- ]?even|partials?\b|trails?\b",
                   "calm markets": r"\bcalm\b|VIX\s*<\s*1[5-8]|RTH range",
                   "wild markets": r"RTH range|wild|volatil",
                   "VIX under 15": r"VIX\s*<\s*1[5-8]|VIX level"}
LAB_FEATURE = {"calm markets": ("rth_rng", "range"), "wild markets": ("rth_rng", "range"), "VIX under 15": ("vix",)}


def rejected_before(kind: str, strat: str, root: str = ROOT):
    """The first place that says this kind of change was already tested and rejected (docs/TESTED_AND_REJECTED.md body, the
    ZEUS Lab registry's rejected_forever blocks), or None. Rejected ideas are watched, never proposed again."""
    lab_bot = {"zlarior": "lit", "atlas": "atlas"}.get(strat)
    reg = _read_json(os.path.join(root, "research", "lab", "zeus_lab", "registry.json"), {}) or {}
    for f in reg.get("rejected_forever") or []:
        b = f.get("blocks") if isinstance(f, dict) else None
        if isinstance(b, dict) and b.get("bot") == lab_bot and b.get("feature") in LAB_FEATURE.get(kind, ()):
            return f"ZEUS Lab: {f.get('title')}"
    pat = REJECT_PATTERNS.get(kind)
    if not pat:
        return None
    try:
        with open(os.path.join(root, "docs", "TESTED_AND_REJECTED.md"), encoding="utf-8") as fh:
            txt = fh.read()
    except OSError:
        return None
    m = re.search(pat, txt, re.I)
    if not m:
        return None
    heads = [h for h in re.finditer(r"^- \*\*(.+?)\*\*", txt[:m.start()], re.M)]
    head = re.sub(r"\s*\(.*$", "", heads[-1].group(1)).rstrip(":").strip() if heads else "Tested and rejected"
    return f"Tested and rejected: {head}"


# ================================================================================================ one strategy
def futures_block(strat: str, T: list, facts: dict, day: str, light=None, brk=None, tw=None, root: str = ROOT) -> dict:
    today = [t for t in T if t["day"] == day]
    live_today = [t for t in today if t["mode"] in ("live", "sim")]
    roll = rolling(T)
    an = anatomy(T)
    fl = fills(T)
    rg = regime_split(T, facts)
    blk = {"name": NAMES[strat], "today": {"n": len(today), "usd": round(sum(t["usd"] for t in today), 2),
                                           "paper": bool(today) and not live_today,
                                           "trades": [{k: t.get(k) for k in ("dir", "usd", "r", "mfe_r", "mae_r", "reason", "slip_ticks", "accounts")}
                                                      for t in today][:8]},
           "roll": roll, "anatomy": an, "fills": fl, "regime": rg}
    # edge light: edge health for Zlarior / ATLAS, its own rolling numbers otherwise
    r20 = roll["20"]
    if light:
        blk["edge"] = {"light": light[0], "src": light[1], "data_to": light[2]}
    elif r20.get("n", 0) >= 10:
        pf = r20.get("pf")
        blk["edge"] = {"light": "GREEN" if pf is None or pf >= 1.2 else "AMBER" if pf >= 1.0 else "RED",
                       "src": f"its own last {r20['n']} trades (PF {pf if pf is not None else 'no loss'})"}
    else:
        blk["edge"] = {"light": None, "src": f"only {r20.get('n', 0)} trades so far"}
    if tw:
        blk["twin"] = tw
    if brk:
        v = brk.get("v") or {}
        blk["breaker"] = {k: v.get(k) for k in ("level", "gap_usd", "gap_r", "n", "missed", "note")}
    flags, watch, props = [], [], []
    wk = dt.date.fromisoformat(day).isocalendar()
    wkey = f"{wk[0]}w{wk[1]:02d}"
    lvl = (blk.get("breaker") or {}).get("level")
    if lvl in ("size_down", "pause"):
        flags.append("breaker says " + ("HALF size" if lvl == "size_down" else "PAUSE") + " (advice already sent)")
    if (tw or {}).get("missed_pc_on"):
        flags.append(f"missed {tw['missed_pc_on']} backtest trade(s) with the PC on")
    for name in rg["slipping"]:
        g = rg["groups"][name]
        why = rejected_before(name, strat, root)
        watch.append(f"slipping in {name}" if name.endswith("markets") else f"slipping with {name}")
        if why:
            blk.setdefault("notes", []).append(f"{name}: {g['n']} trades avg {g['avg']}{g['unit']} vs {g['rest_avg']} the rest; "
                                               f"a rule for it was {why.lower()}: watching only")
        else:
            props.append({"id": f"learn-{strat}-{name.split()[0].lower()}-{wkey}", "kind": "regime",
                          "question": f"{NAMES[strat]}: let Claude test a smaller size in {name}?",
                          "why": f"Its last {min(40, len(T))} trades: {g['n']} in {name} averaged {g['avg']}{g['unit']} "
                                 f"({usd(g['usd'])}), the rest {g['rest_avg']}.",
                          "impact": f"Not known until tested: {usd(g['usd'])} on those {g['n']} trades."})
    pf40, n40 = roll["40"].get("pf"), roll["40"].get("n", 0)
    if n40 >= EDGE_N and pf40 is not None and pf40 < 1.0 and blk["edge"].get("light") != "GREEN":
        watch.append(f"last {n40} trades PF {pf40}")
        props.append({"id": f"learn-{strat}-edge-{wkey}", "kind": "edge",
                      "question": f"{NAMES[strat]}: let Claude re-test it on the newest bars (its last {n40} trades lost)?",
                      "why": f"Last {n40} trades: PF {pf40}, {usd(roll['40'].get('usd'))}, win {roll['40'].get('win')}%; "
                             f"edge light {blk['edge'].get('light') or 'n/a'}.",
                      "impact": f"{usd(roll['40'].get('usd'))} over those {n40} trades."})
    if fl["n"] >= SLIP_MIN and (fl["entry_slip_med"] or 0) > SLIP_PROPOSE:
        watch.append(f"entries fill {fl['entry_slip_med']:+.1f} ticks worse")
        props.append({"id": f"learn-{strat}-cost-{wkey}", "kind": "cost",
                      "question": f"{NAMES[strat]}: let Claude re-run its gates with the real fill cost ({fl['entry_slip_med']:+.1f} ticks)?",
                      "why": f"The last {fl['n']} NinjaTrader entries filled a median {fl['entry_slip_med']:+.1f} ticks worse than "
                             f"planned; the backtest assumes 1 tick.",
                      "impact": f"About {usd(-cost_month(fl['entry_slip_med'], T))} a month at today's size (2.5 trades a week)."})
    if an["losers"] >= 6 and an["turned"] >= 0.6 * an["losers"]:
        why = rejected_before("turned", strat, root)
        watch.append(f"{an['turned']} of {an['losers']} losers were up +{TURN_R:g}R first")
        if why:
            blk.setdefault("notes", []).append(f"losers that turned: a break-even / exit rule was {why.lower()}: watching only")
        else:
            props.append({"id": f"learn-{strat}-turned-{wkey}", "kind": "turned",
                          "question": f"{NAMES[strat]}: let Claude test an exit for trades that were up +{TURN_R:g}R and turned?",
                          "why": an["say"], "impact": "Not known until tested: $0 changes before a yes."})
    blk["flags"], blk["watch"], blk["proposals"] = flags, watch, props
    blk["verdict"] = verdict(flags, watch, props)
    return blk


def cost_month(slip_ticks: float, T: list) -> float:
    """$ a month the median entry slippage costs: ticks x $0.50 a micro-tick x the median micros x 2.5 trades a week x 4.33."""
    q = _med([t["qty"] for t in T[-20:] if t.get("qty")]) or 1
    return round(float(slip_ticks) * TICK * PV * q * 2.5 * 4.33, 2)


def k8_block(K: dict, day: str) -> dict | None:
    """K8 Kalshi clock bets: paper (always) + live (when armed): today, rolling win rate vs the kill rule (58% after 60 live bets)
    and the held-out 68%, the average price paid (kill: over 58c on the last 30), live vs paper of the same windows."""
    if not K:
        return None
    paper = [r for r in K.get("paper") or [] if r.get("result") in ("won", "lost")]
    live = [r for r in K.get("live") or [] if r.get("result") in ("won", "lost")]
    use = live if len(live) >= 20 else paper
    src = "live" if use is live else "paper"
    key = lambda r: (_f(r.get("open_t")) or 0, str(r.get("id")))   # noqa: E731

    def st(rs):
        if not rs:
            return {"n": 0}
        w = sum(1 for r in rs if r["result"] == "won")
        cost = sum(_f(r.get("cost")) or 0 for r in rs)
        net = round(sum(_f(r.get("pnl")) or 0 for r in rs), 2)
        return {"n": len(rs), "win": round(100.0 * w / len(rs), 1), "usd": net, "per_dollar": round(net / cost, 3) if cost else None}
    use = sorted(use, key=key)
    tp = [r for r in paper if r.get("day") == day]
    tl = [r for r in live if r.get("day") == day]
    price = [_f(r.get("price")) for r in use[-30:] if _f(r.get("price"))]
    pm = round(sum(price) / len(price), 3) if price else None
    roll = {str(n): st(use[-n:]) for n in WINDOWS}
    r40 = roll["40"]
    light = None
    if r40.get("n", 0) >= 20:
        w = r40["win"] / 100.0
        light = "GREEN" if w >= 0.62 else "AMBER" if w >= K8_KILL_RATE else "RED"
    pmap = {r.get("id"): r for r in paper}
    tw = [{"id": r.get("id"), "same": (pmap.get(r.get("id")) or {}).get("result") == r.get("result"),
           "price_gap_c": round(100 * ((_f(r.get("price")) or 0) - (_f((pmap.get(r.get("id")) or {}).get("price")) or 0)), 1)}
          for r in live[-20:] if r.get("id") in pmap]
    flags, watch = [], []
    auto, props = k8_adapt(K.get("adapt"), day)
    if auto:
        flags.append("auto: " + "; ".join(a["short"] for a in auto)[:140])
    if pm is not None and len(price) >= 10 and pm > K8_KILL_PRICE - 0.02:
        watch.append(f"fills creeping up ({100 * pm:.0f}c average, kill at {100 * K8_KILL_PRICE:.0f}c)")
    if light == "RED":
        watch.append(f"won {r40['win']:.0f}% of the last {r40['n']} (kill rule under {100 * K8_KILL_RATE:.0f}%)")
    blk = {"name": NAMES["k8"], "src": src, "today": {"n": len(tl) or len(tp), "usd": round(sum(_f(r.get("pnl")) or 0 for r in (tl or tp)), 2),
                                                        "paper": not tl, "won": sum(1 for r in (tl or tp) if r["result"] == "won")},
           "roll": roll, "edge": {"light": light, "src": f"its own last {r40.get('n', 0)} {src} bets (held-out {100 * K8_HELD_OUT_RATE:.0f}%)"},
           "fills": {"n": len(price), "avg_price": pm, "kill_price": K8_KILL_PRICE},
           "twin": {"n": len(tw), "same_result": sum(1 for x in tw if x["same"]), "price_gap_c_med": _med([x["price_gap_c"] for x in tw])},
           "flags": flags, "watch": watch, "proposals": props, "auto": auto}
    blk["verdict"] = verdict(flags, watch, props)
    return blk


def k8_adapt(ad, day: str) -> tuple:
    """engine/kalshi_adapt's weekly re-test (data/kalshi_live/clock_adapt.json, written by the PC itself): the cuts it made in the
    7 days up to `day` (automatic, only ever smaller: half size / OFF / a lower max price) and its open asks for the owner
    (restore a recovered leg), each one ready for the Decide card."""
    if not isinstance(ad, dict):
        return [], []
    try:
        lo = (dt.date.fromisoformat(day) - dt.timedelta(days=7)).isoformat()
    except ValueError:
        return [], []
    auto = [{"day": c.get("day"), "leg": c.get("leg"), "what": c.get("what"), "short": str(c.get("short") or c.get("leg"))[:70],
             "text": str(c.get("text") or "")[:240]}
            for c in ad.get("changes") or [] if isinstance(c, dict) and lo < str(c.get("day") or "") <= day]
    props = []
    for p in ad.get("proposals") or []:
        if isinstance(p, dict) and str(p.get("id") or "").startswith("k8-") and p.get("question") and p.get("why"):
            props.append({"id": p["id"], "question": p["question"], "why": p["why"], "impact": p.get("impact"), "decide_item": p})
    return auto, props


def verdict(flags, watch, props) -> str:
    if flags:
        return flags[0]
    if props:
        return f"{len(props)} idea{'s' if len(props) != 1 else ''} for you to decide"
    if watch:
        return f"{watch[0]}: watching"
    return "nothing to change"


# ================================================================================================ the night
def build(days: list, days_dir: str | None = None, root: str = ROOT, now=None, edge=None, brk=None, k8=None, review=None,
          hide=None) -> dict:
    """The whole scorecard. days = engine/datapipe.load_days bundles, oldest first, the learned day last. Pure apart from the
    files it is pointed at (bars in days_dir; VIX, edge, breaker, K8, registry under root); tests pass every input."""
    now = int(now if now is not None else time.time())
    days = [b for b in days or [] if b.get("day")]
    day = days[-1]["day"] if days else _et(now).date().isoformat()
    vix = vix_closes(root)
    facts = day_facts(days, days_dir, vix)
    bars_today, secs = read_bars(os.path.join(days_dir, day)) if days_dir else ([], 60)
    T = signals(days)
    bar_cache = {day: (bars_today, secs)}
    for t in T[-80:]:                                   # the anatomy's paths on each trade's own day bars
        if t["day"] not in bar_cache:
            bar_cache[t["day"]] = read_bars(os.path.join(days_dir, t["day"])) if days_dir else ([], 60)
        t.update(path(t, *bar_cache[t["day"]]))
    edge = edge_lights(root, now) if edge is None else edge
    brk = breaker(root) if brk is None else brk
    k8 = k8_rows(root) if k8 is None else k8
    hide = hidden(root) if hide is None else set(hide)
    tw_z = None
    try:
        from .zeus_review import twin_block
        tw = twin_block(days)
        tw_z = {k: tw.get(k) for k in ("verdict", "text", "matched", "missed", "extra", "missed_pc_on", "missed_usd", "slip_usd",
                                       "exec_usd", "recent_n", "recent_entry_slip_med", "recent_exit_slip_med")}
    except Exception:
        tw_z = None
    bots = {}
    for s in ("zlarior", "atlas", "blitz"):
        Ts = [t for t in T if t["strat"] == s]
        tw = tw_z if s == "zlarior" else None
        if s == "atlas" and brk.get("atlas"):
            pairs = [p for p in brk["atlas"].get("pairs") or [] if p.get("entry_t") and _et(p["entry_t"]).date().isoformat() <= day]
            tw = {"pairs": len(pairs), "live_r": round(sum(p["live_r"] for p in pairs[-10:]), 2),
                  "twin_r": round(sum(p["twin_r"] for p in pairs[-10:]), 2), "gap_usd": round(sum(p["gap_usd"] for p in pairs[-10:]), 2)}
        if not Ts and s == "blitz":
            continue
        bots[s] = futures_block(s, Ts, facts, day, edge.get(s), brk.get(s), tw, root)
    kb = k8_block(k8, day)
    if kb:
        bots["k8"] = kb
    for s, b in bots.items():
        b["hidden"] = s in hide
    props = [{**p, "bot": s, "day": day} for s, b in bots.items() if not b["hidden"] for p in b.get("proposals") or []]
    acts = [i for i in ((review or {}).get("items") or []) if i.get("level") == "act"]
    S = {"v": VERSION, "kind": "zeus-learned", "day": day, "t": now, "sessions": len(days),
         "regime": {**(facts.get(day) or {}), "tag": regime_tag(facts.get(day) or {})},
         "bots": bots, "proposals": props,
         "auto_changes": [{"bot": "k8", **a} for a in ((bots.get("k8") or {}).get("auto") or []) if not (bots.get("k8") or {}).get("hidden")],
         "adaptations": [{"rule": "engine/circuit_breaker live-vs-twin advice", "bot": s, "level": (b.get("breaker") or {}).get("level")}
                         for s, b in bots.items() if b.get("breaker")],
         "review_acts": [i.get("text") for i in acts][:3],
         "rule": "Research + advice only: ZEUS changed nothing. New ideas are Decide-card proposals (let Claude test it?); the "
                 "approved automatic advice (circuit breaker, edge light) runs as before."}
    S["line"] = line(S)
    return S


def bot_words(s: str, b: dict) -> str:
    td = b.get("today") or {}
    if s == "k8":
        today = (f"{td['n']} bet{'s' if td['n'] != 1 else ''} {usd(td['usd'])}" + (" (paper)" if td.get("paper") else "")) if td.get("n") \
            else "no bets"
    else:
        today = (f"{td['n']} trade{'s' if td['n'] != 1 else ''} {usd(td['usd'])}" + (" (paper)" if td.get("paper") else "")) if td.get("n") \
            else "no trade"
    lt = (b.get("edge") or {}).get("light")
    return f"{b['name']} {today}" + (f", edge {lt}" if lt else "") + f", {b.get('verdict') or 'nothing to change'}"


def line(S: dict, prefix: bool = True) -> str:
    parts = [bot_words(s, b) for s, b in (S.get("bots") or {}).items() if not b.get("hidden")]
    txt = " · ".join(parts) or "no strategy data yet"
    return ((f"ZEUS learned {_md(S.get('day'))}: " if prefix else "") + txt)[:LINE_MAX]


def tiny(S: dict) -> dict:
    """<= TINY_MAX bytes for the PC status ext ("zl"): {"d": day, "t": built, "s": the line without its prefix, "p": proposals}."""
    out = {"d": S.get("day"), "t": int(S.get("t") or 0), "s": line(S, prefix=False), "p": len(S.get("proposals") or [])}
    while _bytes(out) > TINY_MAX and len(out["s"]) > 20:
        out["s"] = out["s"][:max(20, len(out["s"]) - max(4, _bytes(out) - TINY_MAX + 1))].rstrip(" ,·") + "…"
    return out


def read_tiny(path: str | None = None, now=None, max_age_s: int = 4 * 86400) -> dict | None:
    """logs/learn/tiny.json for tools/pc_report (the status ext "zl"), or None (missing / bad / too big / older than 4 days)."""
    try:
        d = _read_json(path or os.path.join(OUT, "tiny.json"), None)
        if not isinstance(d, dict) or not isinstance(d.get("s"), str) or _bytes(d) > TINY_MAX:
            return None
        if (now if now is not None else time.time()) - int(d.get("t") or 0) > max_age_s:
            return None
        return d
    except Exception:  # noqa: BLE001
        return None


def public(S: dict) -> dict:
    """The day folder's learn.json (it rides the data feed): hidden bots left out, per-trade rows dropped, account text scrubbed."""
    out = json.loads(json.dumps(S, default=str))
    out["bots"] = {k: v for k, v in (out.get("bots") or {}).items() if not v.get("hidden")}
    for v in out["bots"].values():
        (v.get("today") or {}).pop("trades", None)
    out["adaptations"] = [a for a in out.get("adaptations") or [] if a.get("bot") in out["bots"]]
    try:
        from .datapipe import scrub
        out = scrub(out)
    except Exception:
        pass
    return out


# ================================================================================================ PC side
def _push(text: str, title: str, now, env=None) -> tuple:
    """ONE push on the PC's private ntfy topic (tools/pc_report config), type daily_summary, no sound in quiet hours. Never raises."""
    try:
        e = os.environ if env is None else env
        if e.get("LE_PR_NO_NET") == "1":
            return False, "network off (tests)"
        from . import notify as N
        s = N.settings()
        if not N.on("daily_summary", s):
            return False, "daily_summary pushes are off (notify_settings.json)"
        from tools import pc_report as PR
        cfg = PR.load_cfg(env)
        if not cfg.get("on") or not cfg.get("topic"):
            return False, "no private alert topic on this PC"
        return PR.ntfy_post(cfg["ntfy"], cfg["topic"], text, title=title, priority="low" if N.quiet(now, s) else "default", tags="brain")
    except Exception as ex:  # noqa: BLE001
        return False, f"{ex.__class__.__name__}: {str(ex)[:80]}"


def nightly(day: str, days_dir: str, out_dir: str = OUT, now=None, notify=None, review=None, root: str = ROOT,
            day_out: str | None = None, env=None, **build_kw) -> dict:
    """The data pipe's nightly child: build `day` from the local day folders, write logs/learn/, the day folder's learn.json
    and ONE push a night. -> {"learned": S, "pushed": (ok, why) | None}. Raises only on a broken install (the caller catches)."""
    from . import datapipe
    e = os.environ if env is None else env
    now = int(now if now is not None else time.time())
    days = datapipe.load_days(days_dir, upto=day, n=120)
    S = build(days, days_dir, root=root, now=now, review=review, **build_kw)
    _write_json(os.path.join(out_dir, f"{S['day']}.json"), S, indent=1)
    _write_json(os.path.join(out_dir, "latest.json"), S, indent=1)
    _write_json(os.path.join(out_dir, "tiny.json"), tiny(S))
    pub = public(S)
    try:
        _write_json(os.path.join(day_out or os.path.join(days_dir, S["day"]), "learn.json"), pub, indent=1)
    except Exception:
        pass
    qp = os.path.join(out_dir, "proposals.jsonl")
    have = {r.get("id") for r in datapipe._jl_read(qp)}
    new = [p for p in S["proposals"] if p["id"] not in have]
    if new:
        with open(qp, "a", encoding="utf-8") as fh:
            for p in new:
                fh.write(json.dumps(p, default=str) + "\n")
    sp = os.path.join(out_dir, "sent.json")
    sent = _read_json(sp, {}) or {}
    out = {"learned": S, "public": pub, "pushed": None, "new_proposals": len(new)}
    if sent.get("push") != S["day"] and str(e.get("LE_LEARNED_PUSH", "")).strip() != "0":
        r = (notify or (lambda text, title: _push(text, title, now, env)))(S["line"], "ZEUS learned")
        out["pushed"] = r
        if r and r[0]:
            sent["push"] = S["day"]
        sent["last"] = {"t": now, "day": S["day"], "ok": bool(r and r[0]), "why": (r or [None, None])[1]}
        _write_json(sp, sent)
    return out


def main(argv=None) -> int:
    import argparse
    from . import datapipe
    ap = argparse.ArgumentParser(prog="python -m engine.zeus_learn", description="ZEUS learned: the nightly scorecard (read-only)")
    ap.add_argument("--days-dir", default=datapipe.DAYS_DIR)
    ap.add_argument("--day", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    days = datapipe.load_days(a.days_dir, upto=a.day, n=120)
    S = build(days, a.days_dir)
    if a.json:
        print(json.dumps(S, indent=1, default=str))
        return 0
    print(S["line"])
    print(f"  market: {S['regime']['tag']}")
    for s, b in S["bots"].items():
        r = (b.get("roll") or {}).get("20") or {}
        an = (b.get("anatomy") or {}).get("say")
        print(f"  {b['name']:8s} last {r.get('n', 0)}: win {r.get('win')}%, PF {r.get('pf')}, {usd(r.get('usd'))}"
              + (f"; {an}" if an else "") + (" (hidden)" if b.get("hidden") else ""))
        for n in b.get("notes") or []:
            print(f"           {n}")
    for p in S["proposals"]:
        print(f"  [decide] {p['question']}")
    print("Advice only: nothing here changes a bot, a size or an order.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
