#!/usr/bin/env python3
"""SIBYL results: closes the loop for Sibyl's own paper ledger. SUGGESTIONS ONLY: it reads two local files and writes one JSON; it never calls Kalshi, never places a bet, never touches the bot.

    python tools/money/sibyl_results.py --state DIR/sibyl_forward.json --out DIR/sibyl_results.json [--ledger tools/web_public/kalshicity/ledger.json]
    python tools/money/sibyl_results.py --selftest

What carries outcomes: `kalshicity/ledger.json` (made by the Kalshi study from the public kalshi.json feed) lists the bot's own SETTLED bets, each with its ticker, strategy, coin, side,
price, contracts and the real net P&L after fees (`pnl`). Nothing else published carries a per-market outcome (edges.json / whatif.json hold totals only).

How a paper pick is settled (a PROXY, said plainly everywhere): a Sibyl pick is a KIND of bet ("95-97c", "Bitcoin", "buying NO", "08-12 ET", "15-min favourites", or a combination with " · ").
It is not one named market. So an open paper pick is settled by the real outcome of the FIRST bet of the bot that
  * was settled on or after the pick's day (New York day of the bet),
  * matches every part of the pick's kind, and
  * has not already settled another pick (each real bet is used once, so overlapping picks never double-count one result).
pnl > 0 = won, otherwise lost. The paper stake and the paper win in sibyl_forward.json are unchanged: only the win / lose answer comes from the real bet. A pick whose kind cannot be read
(an unknown label) or with no matching settled bet yet stays OPEN. Nothing is invented: no match, no result. The ledger file only keeps the bot's most recent settled bets, so very old
open picks may never settle; they stay open and are counted as open.

Output (feeds `sibyl_ledger.py --results`): {"v":1,"kind":"sibyl-results","proxy":true,"asof","source","results":[{"id","outcome":"won"|"lost","ticker","bot_pnl"}],"open":n,"note"}.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "tools", "web_public", "kalshicity", "ledger.json")
NOTE = ("A proxy: each paper pick is settled by the real result of the bot's first settled bet of the same kind on or after the pick's day (each real bet used once). "
        "It is not the paper bet itself, and a bet the bot never made cannot settle a pick.")


def num(v):
    if isinstance(v, bool):
        return None
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            j = json.load(fh)
        return j if isinstance(j, dict) else None
    except (OSError, ValueError):
        return None


def et_parts(t):
    """(YYYY-MM-DD, hour) in New York for an epoch second; (None, None) when the time zone data is missing."""
    try:
        from zoneinfo import ZoneInfo
        d = dt.datetime.fromtimestamp(t, ZoneInfo("America/New_York"))
        return d.strftime("%Y-%m-%d"), d.hour
    except Exception:
        return None, None


def part_matches(part, tr, hour):
    """does one part of a pick's kind describe this settled bet? None = the part is not understood."""
    p = part.strip()
    low = p.lower()
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)\s*¢", p) or re.search(r"(\d+)\s*[–-]\s*(\d+)c\b", p)
    if m and "et" not in low.split():
        a, b = int(m.group(1)) / 100, int(m.group(2)) / 100
        px = num(tr.get("p"))
        return None if px is None else a <= px < b
    m = re.search(r"under\s+(\d+)\s*¢", p) or re.search(r"<\s*(\d+)c\b", p)
    if m:
        px = num(tr.get("p"))
        return None if px is None else px < int(m.group(1)) / 100
    m = re.search(r"(\d+)\s*¢\s+and up", p) or re.search(r"(\d+)c\+", p)
    if m:
        px = num(tr.get("p"))
        return None if px is None else px >= int(m.group(1)) / 100
    m = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})\s*ET", p)
    if m:
        if hour is None:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        return a <= hour < b
    if low in ("buying no", "no side", "no"):
        return str(tr.get("sd")).lower() == "no"
    if low in ("buying yes", "yes side", "yes"):
        return str(tr.get("sd")).lower() == "yes"
    if p and (p == tr.get("s") or p == tr.get("m")):
        return True
    return False if p and (tr.get("s") or tr.get("m")) and p not in ("*",) and _known_name(p, tr) else None


def _known_name(p, tr):
    """a plain name (strategy / coin): it is understood as 'does not match' only if it looks like a name, not a label we cannot parse."""
    return not re.search(r"\d", p)


def kind_matches(title, tr, hour):
    """True / False when every part is understood; None when any part is not (the pick then stays open)."""
    res = [part_matches(x, tr, hour) for x in str(title).split("·")]
    if any(r is None for r in res):
        return None
    return all(res)


def build(state, ledger, now=None):
    bets = [b for b in (state.get("bets") if isinstance(state, dict) else None) or [] if isinstance(b, dict) and b.get("status") == "open"]
    trades = sorted([t for t in (ledger.get("trades") if isinstance(ledger, dict) else None) or [] if isinstance(t, dict) and num(t.get("t")) and num(t.get("pnl")) is not None], key=lambda t: t["t"])
    used, out = set(), []
    for b in sorted(bets, key=lambda x: x.get("day") or ""):
        for i, tr in enumerate(trades):
            if i in used:
                continue
            day, hour = et_parts(tr["t"])
            if day is None or day < str(b.get("day") or "9999"):
                continue
            ok = kind_matches(b.get("title", ""), tr, hour)
            if ok:
                used.add(i)
                out.append({"id": b["id"], "outcome": "won" if tr["pnl"] > 0 else "lost", "ticker": str(tr.get("k", ""))[:40], "bot_pnl": round(tr["pnl"], 2)})
                break
    asof = dt.datetime.fromtimestamp(now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp(), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"v": 1, "kind": "sibyl-results", "proxy": True, "asof": asof, "source": "kalshicity/ledger.json (the bot's settled bets)", "results": out, "open": len(bets) - len(out), "note": NOTE}


def run(state_path, out_path, ledger_path=LEDGER):
    """-> (exit code, message). 0 also when there is nothing to do; 2 only for a damaged state file."""
    ledger = load(ledger_path)
    if not ledger or not isinstance(ledger.get("trades"), list):
        return 0, f"no settled-bet data at {ledger_path}: no result written (Sibyl's picks simply stay open; nothing is invented)"
    if not os.path.exists(state_path):
        return 0, "no sibyl_forward.json yet: nothing to settle"
    state = load(state_path)
    if not state or not isinstance(state.get("bets"), list):
        return 2, "sibyl_forward.json is damaged: nothing written"
    res = build(state, ledger)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, out_path)
    return 0, f"{len(res['results'])} pick(s) settled by real bets, {res['open']} still open. {NOTE}"


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    bad = []

    def ck(name, ok, info=""):
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))
        if not ok:
            bad.append(name)
    t0 = 1793526729   # 2026-11-01 04:12 ET
    tr = {"k": "KXBTCD-26NOV0105", "s": "Late favourite (BTC hourly)", "m": "Bitcoin", "sd": "no", "p": 0.98, "c": 6.0, "pnl": 0.11, "t": t0}
    _, h = et_parts(t0)   # hour 4 (EST: the clocks went back that morning)
    K = ("at 97–99¢", "at 95–97¢", "under 99¢", "98¢ and up", "buying NO", "buying YES", "04-08 ET", "08-12 ET", "Late favourite (BTC hourly)", "Bitcoin", "XRP")
    ck("kinds: a price band, under / and up, a side, an ET hour window, a strategy, a coin", [kind_matches(x, tr, h) for x in K] == [True, False, True, True, True, False, True, False, True, True, False], [kind_matches(x, tr, h) for x in K])
    ck("a combination needs every part; an unreadable part gives None (the pick stays open)", kind_matches("Bitcoin · buying NO", tr, h) is True and kind_matches("Bitcoin · buying YES", tr, h) is False and kind_matches("Mystery 7 thing", tr, h) is None)
    state = {"bets": [{"id": "2026-11-01|at 97–99¢", "day": "2026-11-01", "title": "at 97–99¢", "status": "open"},
                      {"id": "2026-11-01|Bitcoin", "day": "2026-11-01", "title": "Bitcoin", "status": "open"},
                      {"id": "2026-11-02|buying YES", "day": "2026-11-02", "title": "buying YES", "status": "open"},
                      {"id": "2026-11-01|Weird 9", "day": "2026-11-01", "title": "Weird 9", "status": "open"},
                      {"id": "2026-11-01|done", "day": "2026-11-01", "title": "Bitcoin", "status": "won"}]}
    ledger = {"trades": [tr, {"k": "B", "s": "15-min favourites", "m": "Bitcoin", "sd": "yes", "p": 0.96, "c": 10, "pnl": -5.2, "t": t0 + 3600}, {"k": "C", "s": "x", "m": "Other", "sd": "yes", "p": 0.5, "c": 1, "pnl": 0.3, "t": t0 + 4 * 86400}]}
    r = build(state, ledger, now=t0)
    by = {x["id"]: x for x in r["results"]}
    ck("settling: the first matching bet; a real bet is used once (the second Bitcoin pick takes the NEXT Bitcoin bet); a later day waits for a later bet; unknown kinds and settled picks are left alone",
       by["2026-11-01|at 97–99¢"]["outcome"] == "won" and by["2026-11-01|Bitcoin"]["outcome"] == "lost" and by["2026-11-01|Bitcoin"]["ticker"] == "B" and by["2026-11-02|buying YES"]["ticker"] == "C" and "2026-11-01|Weird 9" not in by and len(by) == 3 and r["open"] == 1, r)
    ck("the file says it is a proxy and why", r["proxy"] is True and "proxy" in r["note"].lower() and r["kind"] == "sibyl-results")
    ck("a pick is never settled by a bet from before its day", build({"bets": [{"id": "x", "day": "2026-11-09", "title": "Bitcoin", "status": "open"}]}, ledger, now=t0)["results"] == [])
    d = tempfile.mkdtemp(prefix="sibyl-res-")
    sp, lp, op = os.path.join(d, "sibyl_forward.json"), os.path.join(d, "ledger.json"), os.path.join(d, "sibyl_results.json")
    json.dump({"v": 1, "bets": state["bets"]}, open(sp, "w"))
    code, msg = run(sp, op, os.path.join(d, "none.json"))
    ck("no settled-bet file: exit 0, says why, writes nothing, invents nothing", code == 0 and not os.path.exists(op) and "no settled-bet data" in msg, msg)
    json.dump(ledger, open(lp, "w"))
    code, msg = run(sp, op, lp)
    ck("a real run writes the results file", code == 0 and os.path.isfile(op) and len(json.load(open(op))["results"]) == 3, msg)
    ck("no sibyl_forward.json yet: exit 0, nothing to settle", run(os.path.join(d, "x.json"), op, lp)[0] == 0)
    open(sp, "w").write("{broken")
    ck("a damaged state file: exit 2, nothing written", run(sp, os.path.join(d, "o2.json"), lp)[0] == 2 and not os.path.exists(os.path.join(d, "o2.json")))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("sl", os.path.join(os.path.dirname(os.path.abspath(__file__)), "sibyl_ledger.py"))
        L = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(L)
        st = L.new_state("2026-11-01")
        st["bets"] = [{"id": "2026-11-01|at 97–99¢", "day": "2026-11-01", "title": "at 97–99¢", "type": "Price band", "stake_usd": 3.41, "win_usd": 0.12, "status": "open", "pnl_usd": None, "r": None, "settled_day": None}]
        n = L.settle(st, {"results": build(st, ledger, now=t0)["results"]}, "2026-11-04")
        ck("the loop closes: the ledger settles the pick from this file (won = the paper win, +$0.12)", n == 1 and st["bets"][0]["status"] == "won" and st["bets"][0]["pnl_usd"] == 0.12, st["bets"])
    except Exception as e:  # pragma: no cover
        ck("the loop closes with sibyl_ledger.py", False, e)
    code_txt = open(os.path.abspath(__file__), encoding="utf-8").read().split("# ----", 1)[0]
    ck("never trades or phones out: no network, engine or bot import", not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http|ssl|engine|live)\b", code_txt, re.M))
    print(f"\n{'ALL PASS' if not bad else str(len(bad)) + ' FAILED'}")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sibyl results: settle the paper ledger from the bot's real settled bets (a proxy; suggestions only).")
    ap.add_argument("--state", help="sibyl_forward.json (read only)")
    ap.add_argument("--out", help="results file to write (feeds sibyl_ledger.py --results)")
    ap.add_argument("--ledger", default=LEDGER, help="kalshicity/ledger.json (read only)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.state or not a.out:
        ap.error("--state and --out are required (or --selftest)")
    code, msg = run(a.state, a.out, a.ledger)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
