"""TRADING exporter (night-trading, 2026-11-17): the small trade file the Trading page (tools/web_public/trading/) reads.

Writes tools/web_public/trading/trades.json: every 2026 trade of the two shown bots, one compact row each, with its source said
plainly. Read-only: nothing here decides, sizes or routes a trade. BLITZ is hidden (owner 2026-11-15) and never exported.

Sources (futures only, never Yahoo):
  BACKTEST  LIT    research/lab/backtest_live.json "trades" (the live-settings replay, normal sizing: $800 risk up to a 20-pt stop)
            ATLAS  research/second/ema_best.json, md_best.json, sr_best.json (the three members' research trades, their own sizes)
  PAPER     LIT    research/odeon/cloud_trades.json live.ledger (the cloud's paper twin of Zlarior, a snapshot of the dashboard branch)
  LIVE      LIT    research/odeon/cloud_trades.json accounts[] (the PC's closed MFFU eval trades from its heartbeat)
  replay    tools/web_public/odeon/trades.json ids: a row whose trade Odeon can play gets "odeon" = that reel id
  twin      a LIVE row gets the PAPER trade with the same entry minute ("twin"), and the BACKTEST trade within 10 minutes when there is one
The page adds the PC's newest trades from ../home.json (board.trades) at run time; this file is the history.
Same inputs give the same bytes (no clock, sorted keys, fixed rounding).

  python tools/trading_export.py            # -> tools/web_public/trading/trades.json
  python tools/trading_export.py --check    # exit 1 when the file is stale
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "trading", "trades.json")
BT = os.path.join(ROOT, "research", "lab", "backtest_live.json")
CLOUD = os.path.join(ROOT, "research", "odeon", "cloud_trades.json")
ODEON = os.path.join(ROOT, "tools", "web_public", "odeon", "trades.json")
ATLAS = (("EMA", "research/second/ema_best.json"), ("MACD", "research/second/md_best.json"), ("S/R", "research/second/sr_best.json"))
ET = ZoneInfo("America/New_York")
FROM = "2026-01-01"
PERIODS = {"h1": "2026 H1 (picked on)", "h2": "2026 H2 (check)"}


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def r2(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, 2) if v == v else None


def et(t: int):
    return dt.datetime.fromtimestamp(int(t), ET)


def row(bot, acct, src, t: dict, member=""):
    e_t = int(t["t"])
    d = et(e_t)
    side = "SHORT" if str(t["side"]).upper().startswith("S") or t.get("dir") == -1 else "LONG"
    risk = r2(t.get("risk_usd"))
    return {"id": f"{src}.{bot.lower()}.{d:%Y-%m-%d_%H%M}_{side.lower()}{'_' + re.sub(r'[^a-z]', '', member.lower()) if member else ''}",
            "bot": bot, "acct": acct, "src": src, "m": member, "day": t.get("day") or f"{d:%Y-%m-%d}", "hm": f"{d:%H:%M}",
            "t": e_t, "xt": int(t["xt"]) if t.get("xt") else None, "side": side, "q": int(t.get("q") or 1),
            "e": r2(t.get("e")), "s": r2(t.get("s")), "tg": r2(t.get("tg")), "x": r2(t.get("x")),
            "k": str(t.get("k") or "").upper()[:12], "usd": r2(t.get("usd")) or 0.0, "r": r2(t.get("r")), "risk": risk}


def backtest_lit(bt: dict) -> list:
    out = []
    for t in bt.get("trades") or []:
        if str(t.get("day")) < FROM or not t.get("entry_t"):
            continue
        out.append(row("LIT", "zlarior", "backtest", {"t": t["entry_t"], "xt": t.get("exit_t"), "side": t["side"], "day": t["day"],
                                                     "q": t.get("qty_total") or t.get("qty"), "e": t.get("entry"), "s": t.get("stop"),
                                                     "tg": t.get("target"), "x": t.get("exit_price"), "k": t.get("exit"),
                                                     "usd": t.get("pnl"), "r": t.get("r"), "risk_usd": t.get("risk_usd")}))
    return out


def backtest_atlas() -> list:
    out = []
    for member, path in ATLAS:
        d = _load(os.path.join(ROOT, path), {}) or {}
        for t in d.get("trades") or []:
            if str(t.get("day")) < FROM or not t.get("entry_t") or not t.get("exit_t"):
                continue
            risk = abs(float(t["entry"]) - float(t["stop"])) * 2 * int(t.get("qty") or 1)
            out.append(row("ATLAS", "atlas", "backtest", {"t": t["entry_t"], "xt": t["exit_t"], "side": "SHORT" if int(t["dir"]) < 0 else "LONG",
                                                         "day": t["day"], "q": t.get("qty"), "e": t["entry"], "s": t["stop"], "tg": t["target"],
                                                         "x": t["exit"], "k": t.get("exit_kind"), "usd": t.get("pnl_usd"), "r": t.get("r"),
                                                         "risk_usd": risk}, member))
    return out


def cloud(c: dict):
    data = (c or {}).get("data") or {}
    led = (data.get("live") or {}).get("ledger") or []
    led = list(led.values()) if isinstance(led, dict) else led
    paper, live = [], []
    for v in led:
        if v.get("entry_t") and v.get("exit_ts") and v.get("exit_px") is not None:
            paper.append(row("LIT", "zlarior", "paper", {"t": v["entry_t"], "xt": v["exit_ts"], "side": v["side"], "day": v.get("day"),
                                                        "q": v.get("qty"), "e": v.get("entry_px"), "s": v.get("stop_px"), "tg": v.get("target_px"),
                                                        "x": v.get("exit_px"), "k": v.get("exit"), "usd": v.get("usd"), "r": v.get("R"),
                                                        "risk_usd": (v.get("risk_pts") or 0) * 2 * (v.get("qty") or 1)}))
    for acc in data.get("accounts") or []:
        if acc.get("kind") == "paper" or "paper" in str(acc.get("name", "")).lower() or "blitz" in str(acc.get("name", "")).lower():
            continue
        acct = "atlas" if re.search(r"25k|atlas", str(acc.get("name", "")), re.I) else "zlarior"
        for t in acc.get("trades") or []:
            if t.get("entry_t") and t.get("exit_t") and t.get("exit_px") is not None:
                live.append(row("LIT" if acct == "zlarior" else "ATLAS", acct, "live",
                                {"t": t["entry_t"], "xt": t["exit_t"], "side": t["side"], "day": t.get("day"), "q": t.get("qty"),
                                 "e": t.get("entry"), "s": t.get("stop"), "tg": t.get("target"), "x": t.get("exit_px"), "k": t.get("exit"),
                                 "usd": t.get("pnl"), "r": t.get("r"), "risk_usd": (t.get("risk_pts") or 0) * 2 * (t.get("qty") or 1)}))
    m = re.search(r"as of (\d{9,11})", str((c or {}).get("source") or ""))
    return paper, live, (int(m.group(1)) if m else None)


def build() -> dict:
    bt = _load(BT, {}) or {}
    lit, atl = backtest_lit(bt), backtest_atlas()
    paper, live, snap_t = cloud(_load(CLOUD, {}) or {})
    reels = {}
    for t in (_load(ODEON, {}) or {}).get("trades") or []:
        src = {"real": "live"}.get(t.get("src"), t.get("src"))
        reels[(src, t.get("bot"), int((t.get("entry") or {}).get("t") or 0))] = t.get("id")
    rows = lit + atl + paper + live
    for r in rows:
        r["odeon"] = reels.get((r["src"], r["bot"], r["t"]))
    by_t = {(p["bot"], p["t"] // 60): p for p in paper}
    for r in live:
        tw = {}
        p = by_t.get((r["bot"], r["t"] // 60))
        if p:
            tw["paper"] = {"usd": p["usd"], "r": p["r"], "k": p["k"], "q": p["q"], "side": p["side"]}
        b = next((x for x in (lit if r["bot"] == "LIT" else atl) if abs(x["t"] - r["t"]) <= 600), None)
        if b:
            tw["backtest"] = {"usd": b["usd"], "r": b["r"], "k": b["k"], "q": b["q"], "side": b["side"]}
        r["twin"] = tw or None
    rows.sort(key=lambda r: (r["t"], r["src"], r["bot"], r["m"]))
    seen, uniq = set(), []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        uniq.append(r)
    upto = {}
    for r in uniq:
        k = f"{r['src']}_{r['bot'].lower()}"
        upto[k] = max(upto.get(k, ""), r["day"])
    ref = {}
    for key, name in PERIODS.items():
        p = (bt.get("periods") or {}).get(name)
        if p:
            ref[key] = {k: p.get(k) for k in ("from", "to", "trades", "per_week", "win_pct", "pf", "net", "max_dd", "best_day", "worst_day", "per_month")}
    return {"v": 1, "app": "trading", "from": FROM, "n": len(uniq), "trades": uniq, "upto": upto, "cloud_t": snap_t,
            "lit_ref": ref, "built_from": (bt.get("meta") or {}).get("built"),
            "sources": {"backtest": "BACKTEST: LIT = research/lab/backtest_live.json (the live-settings replay, normal size: $800 risk up to a "
                                    "20-pt stop); ATLAS = research/second/*_best.json (the 3 members' research trades). Replays on TradingView "
                                    "CME NQ1! futures bars, costs in. Not money made.",
                        "paper": "PAPER: the cloud's paper twin of Zlarior (research/odeon/cloud_trades.json, the dashboard branch's ledger).",
                        "live": "LIVE: the PC's closed MFFU eval trades (its heartbeat, same snapshot) plus the newest from home.json."}}


def dump(bundle: dict) -> str:
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when trades.json would change")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    text = dump(build())
    if a.check:
        try:
            with open(a.out, encoding="utf-8") as fh:
                same = fh.read() == text
        except OSError:
            same = False
        print("trades.json is current" if same else "trades.json is STALE: run python tools/trading_export.py")
        return 0 if same else 1
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    b = json.loads(text)
    print(f"wrote {a.out}: {b['n']} trades ({', '.join(f'{k} to {v}' for k, v in sorted(b['upto'].items()))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
