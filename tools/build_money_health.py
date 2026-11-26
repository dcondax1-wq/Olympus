"""Money view + Strategy health data for the phone site (day-site5 2026-11-26). Read only research; changes no bot, no model, no switch.

    python tools/build_money_health.py           writes tools/web_public/business/forecast.json (when the forecaster has landed)
                                                 and tools/web_public/trading/bands.json
    python tools/build_money_health.py --check   exit 1 when either is stale

forecast.json  = research/forecast/forecast.json (the eval pass forecaster, another helper), copied as is (+ "src"). Until it lands NO file is
                 written: the Money view then reads business/payday.json (the payday plan's 1,000 runs) and says so.
                 Expected shape: {"v", "made", "market", "runs", "accounts": {<key or name>: {"name", "p_pass", "p_fail", "days_med", "days_p25",
                 "days_p75", "pass_by", "p_payout", "payout_by", "payout_usd"}}}  (p_* 0..1; dates YYYY-MM-DD).
bands.json     = research/health/bands.json (another helper) when it exists, else a PROVISIONAL band measured here on the backtest trades in
                 tools/web_public/trading/trades.json (src backtest): every run of WINDOW consecutive trades -> the avg R per trade, its
                 5 / 25 / 50 / 75 / 95th percentiles, and the losing-streak percentiles. Shape:
                 {"v", "made", "src", "provisional", "bots": {"lit" | "atlas": {"name", "window", "avg_r": {"p5".."p95"}, "streak_p75", "streak_p95",
                 "n_backtest", "span"}}}
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "tools", "web_public")
FC_SRC = os.path.join(ROOT, "research", "forecast", "forecast.json")
BANDS_SRC = os.path.join(ROOT, "research", "health", "bands.json")
TRADES = os.path.join(PUB, "trading", "trades.json")
FC_OUT = os.path.join(PUB, "business", "forecast.json")
BANDS_OUT = os.path.join(PUB, "trading", "bands.json")
WINDOW = 10
NAMES = {"lit": "LIT (Zlarior)", "atlas": "ATLAS"}


def _load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def pct(xs, q):
    """linear-interpolated percentile (q 0..100) of a sorted list"""
    if not xs:
        return None
    k = (len(xs) - 1) * q / 100.0
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def band_of(rs: list[float], window: int) -> dict | None:
    if len(rs) < window * 2:
        return None
    avgs = sorted(sum(rs[i:i + window]) / window for i in range(len(rs) - window + 1))
    streaks, s = [], 0
    for r in rs:
        if r < 0:
            s += 1
        else:
            if s:
                streaks.append(s)
            s = 0
    if s:
        streaks.append(s)
    streaks.sort()
    r3 = lambda v: round(v, 3) if v is not None else None  # noqa: E731
    return {"avg_r": {k: r3(pct(avgs, q)) for k, q in (("p5", 5), ("p25", 25), ("p50", 50), ("p75", 75), ("p95", 95))},
            "streak_p75": int(round(pct(streaks, 75) or 0)), "streak_p95": int(round(pct(streaks, 95) or 0))}


def from_research(src: dict) -> dict:
    """research/health/bands.json (day-batch5: {made, window, bots: {LIT|ATLAS|BLITZ: {bands: {"2026"|"2021-25": {p5, p50, p95, n_windows,
    trades}}, live: {n, trades: [{day, r, usd}], mean_r, zone}}}}) -> the page's shape (lit / atlas only: BLITZ never on the Trading page).
    The 2026 band is the one the words use; the 2021-25 band rides along as a second line."""
    w = int(src.get("window") or WINDOW)
    out = {"v": 2, "made": str(src.get("made") or "")[:10], "provisional": False, "window": w, "src": "research/health/bands.json", "bots": {}}
    for k, b in (src.get("bots") or {}).items():
        bot = str(k).lower()
        if bot not in NAMES or not isinstance(b, dict):
            continue
        bands_ = b.get("bands") or {}
        main, ref = bands_.get("2026") or {}, bands_.get("2021-25") or {}
        if not all(isinstance(main.get(q), (int, float)) for q in ("p5", "p50", "p95")):
            continue
        live = b.get("live") or {}
        out["bots"][bot] = {"name": NAMES[bot], "window": w, "avg_r": {q: main[q] for q in ("p5", "p50", "p95")}, "n_backtest": main.get("trades"), "n_windows": main.get("n_windows"),
                            "span": "2026", "ref": {"span": "2021-25", **{q: ref.get(q) for q in ("p5", "p50", "p95")}} if ref else None,
                            "live": [{"day": str(t.get("day") or "")[:10], "r": t.get("r"), "usd": t.get("usd")} for t in live.get("trades") or [] if isinstance(t, dict) and isinstance(t.get("r"), (int, float))],
                            "zone": str(live.get("zone") or "")[:80]}
    return out


def bands() -> dict:
    src = _load(BANDS_SRC)
    if isinstance(src, dict) and isinstance(src.get("bots"), dict):
        return from_research(src)
    file = _load(TRADES) or {}
    out = {"v": 1, "made": str(file.get("built_from") or "")[:10], "provisional": True, "window": WINDOW,
           "src": "PROVISIONAL: measured on the backtest trades in trading/trades.json (research/health/bands.json has not landed)", "bots": {}}
    for bot in ("lit", "atlas"):
        rows = sorted((t for t in file.get("trades") or [] if isinstance(t, dict) and str(t.get("bot", "")).lower() == bot and t.get("src") == "backtest"
                       and isinstance(t.get("r"), (int, float)) and isinstance(t.get("t"), (int, float))), key=lambda t: t["t"])
        b = band_of([float(t["r"]) for t in rows], WINDOW)
        if b:
            out["bots"][bot] = {"name": NAMES[bot], "window": WINDOW, **b, "n_backtest": len(rows), "span": f"{rows[0].get('day', '')}..{rows[-1].get('day', '')}"}
    return out


def forecast() -> dict | None:
    src = _load(FC_SRC)
    return {**src, "src": "research/forecast/forecast.json"} if isinstance(src, dict) and isinstance(src.get("accounts"), dict) else None


def _text(d) -> str:
    return json.dumps(d, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def main(argv) -> int:
    want = {BANDS_OUT: _text(bands())}
    fc = forecast()
    if fc is not None:
        want[FC_OUT] = _text(fc)
    if "--check" in argv:
        stale = [p for p, t in want.items() if (open(p, encoding="utf-8").read().strip() if os.path.exists(p) else "") != t]
        print("money / health data " + ("is fresh" if not stale else "is STALE: run python tools/build_money_health.py (" + ", ".join(os.path.relpath(p, ROOT) for p in stale) + ")"))
        return 1 if stale else 0
    for p, t in want.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
        print("wrote " + os.path.relpath(p, ROOT))
    if fc is None:
        print("forecast: research/forecast/forecast.json not there yet: the Money view reads business/payday.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
