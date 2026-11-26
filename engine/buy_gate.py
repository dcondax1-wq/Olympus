"""BUY GATE (big-shadow 2026-11-26; research/writeups/business-planner-2026-11-26.md, research/planner/card.json).
DISPLAY ONLY: it never buys, never blocks an order, never changes sizing. It says "OK to buy" or "STOP buying" new evals.

Two rules from the business planner (pre-registered, real engine, 1,000 paths x 12 months, 4 markets):
  W3  LIT's last 40 trades add up to less than 0R -> STOP     (card stop-buying-tripwire; R = the backtest twin's points / stop)
  W5  the business (payouts to you - eval fees since the gate's start day) is $300 under its own best -> STOP
                                                              (card rapid25-second-with-stop)
After a STOP the rule says OK again only once the SHADOW eval (engine/shadow_eval.py, a free paper Builder 50K) passes on
or after the STOP day; W5 then measures from that day's business $ (a new best). Recomputed from scratch on every run.

Inputs (read only): LIT trades = research/planner/lit_r_seed.json (the stored backtest's last 40 LIT trades to 2026-10-16)
+ the PC's nightly LIT backtest twin (logs/exec_audit/report.json) after it; payouts = data/payout_ledger.json "to_you"
(engine/payout_autopilot.record); eval fees = data/eval_buys.json (record one: python -X utf8 -m engine.buy_gate buy
--plan "Rapid EOD 25K" --price 97.20). Shown only when data/buy_gate.json says {"show": true} (default OFF); "rules" there
picks which rules count for the verdict (default both). Output: logs/buy_gate.json (tiny() rides the PC report as "bg").

    python -X utf8 -m engine.buy_gate                 print the gate (computes even with the switch off)
    python -X utf8 -m engine.buy_gate buy --plan P --price X [--day YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys
import time

from engine import shadow_eval as SE

ROOT = SE.ROOT
SEED = os.path.join(ROOT, "research", "planner", "lit_r_seed.json")
LEDGER = os.path.join(ROOT, "data", "payout_ledger.json")
BUYS = os.path.join(ROOT, "data", "eval_buys.json")
OUT = os.path.join(ROOT, "logs", "buy_gate.json")
SWITCH = SE.SWITCH
N_TRADES, DD_USD = 40, 300.0
RULES = ("W3", "W5")


def lit_r(seed_path=None, report_path=None) -> list:
    """[(day, entry_t, R)] in order: the seed, then twin trades after the seed's last entry."""
    seed = [(str(x["day"]), int(x["entry_t"]), float(x["r"])) for x in (SE._read(seed_path or SEED, []) or [])]
    last = seed[-1][1] if seed else 0
    tw = [(t["day"], t["entry_t"], t["pts"] / t["risk"]) for t in SE.twin_trades(report_path) if t["entry_t"] > last]
    return seed + tw


def tracker_payouts() -> list:
    """Payouts recorded through the OLD per-account CLIs (account_b / eval_life / rapid --payout) never reach the payout ledger
    (red team #19): read the accounts' own trackers too. -> [{key, day, to_you}] (Builder 80%, Rapid 90%). Never raises."""
    out = []
    try:
        from engine import account_b as A
        for d, v in ((A.raw_cfg() or {}).get("payouts") or {}).items():
            out.append({"key": "atlas", "day": str(d), "to_you": float(v) * 0.8})
    except Exception:  # noqa: BLE001
        pass
    try:
        from engine import multi_account as MA
        for r in MA.load_file(MA.ACCOUNTS_PATH) or []:
            for d, v in (((r or {}).get("funded") or {}).get("payouts") or {}).items():
                out.append({"key": f"x:{r.get('id')}", "day": str(d), "to_you": float(v) * 0.8})
    except Exception:  # noqa: BLE001
        pass
    try:
        from engine import rapid as RP
        for slot in ("rapid", "rapid2"):
            blk = RP.read(RP.slot_path(slot)) or {}
            for d, v in (blk.get("payouts") or {}).items():
                out.append({"key": slot, "day": str(d), "to_you": float(v) * RP.SPLIT})
    except Exception:  # noqa: BLE001
        pass
    return out


def biz_by_day(ledger_path=None, buys_path=None, start: str = "", trackers=None) -> dict:
    """{day: payouts to you - eval fees that day} from the gate's start day on. Payouts = the payout ledger + any tracker payout
    the ledger does not have (same account key + day = one payout: engine/payout_autopilot.record writes both)."""
    out = collections.defaultdict(float)
    seen = set()
    for x in (SE._read(ledger_path or LEDGER, {}) or {}).get("rows") or []:
        if isinstance(x, dict) and str(x.get("day", "")) >= start:
            out[str(x["day"])] += float(x.get("to_you") or 0.0)
            seen.add((str(x.get("key")), str(x["day"])))
    for x in (tracker_payouts() if trackers is None else trackers):
        if str(x.get("day", "")) >= start and (str(x.get("key")), str(x["day"])) not in seen:
            out[str(x["day"])] += float(x.get("to_you") or 0.0)
            seen.add((str(x.get("key")), str(x["day"])))
    for x in (SE._read(buys_path or BUYS, {}) or {}).get("rows") or []:
        if isinstance(x, dict) and str(x.get("day", "")) >= start:
            out[str(x["day"])] -= float(x.get("price") or 0.0)
    return dict(out)


def evaluate(R: list, biz: dict, passes: list, start: str, today: str, rules=RULES) -> dict:
    """Walk the days start..today: each rule's STOP / OK state (STOP -> OK only on a shadow pass on / after the STOP day)."""
    days = sorted(set(SE.sessions(start, today)) | {d for d in biz if start <= d <= today})
    pas = sorted(passes)
    r40 = [r for d, _, r in R if d < start][-N_TRADES:]
    later = [(d, r) for d, _, r in R if d >= start]
    i = 0
    cum, peak = 0.0, 0.0
    st = {"W3": {"stop": False, "since": None}, "W5": {"stop": False, "since": None}}
    for day in days:
        while i < len(later) and later[i][0] <= day:
            r40 = (r40 + [later[i][1]])[-N_TRADES:]
            i += 1
        cum += biz.get(day, 0.0)
        peak = max(peak, cum)
        for k in ("W3", "W5"):
            s = st[k]
            if s["stop"]:
                if not any(p >= s["since"] and p <= day for p in pas):
                    continue
                s["stop"], s["since"] = False, None        # a shadow pass lifts it; the same day's check below can set it again
                if k == "W5":                              # (as the planner: research/planner/planner.py run_path)
                    peak = cum
            if k == "W3" and len(r40) >= N_TRADES and sum(r40) < 0:
                s["stop"], s["since"] = True, day
            if k == "W5" and cum < peak - DD_USD:
                s["stop"], s["since"] = True, day
    use = [k for k in rules if k in st]
    stop = any(st[k]["stop"] for k in use)
    return {"verdict": "STOP" if stop else "OK", "rules": use, "w3": {"sum40": round(sum(r40), 1), "n": len(r40), **st["W3"]},
            "w5": {"biz": round(cum, 2), "peak": round(peak, 2), "under": round(peak - cum, 2), **st["W5"]}}


def line(g: dict, sh: dict | None = None) -> str:
    w3, w5 = g["w3"], g["w5"]
    head = "Buy gate: OK to buy new evals" if g["verdict"] == "OK" else "Buy gate: STOP buying new evals"
    parts = []
    if "W3" in g["rules"]:
        parts.append(f"LIT last {w3['n']} trades {w3['sum40']:+.1f}R" + (f" (STOP since {w3['since']})" if w3["stop"] else ""))
    if "W5" in g["rules"]:
        parts.append(f"business {SE.usd(w5['biz'])}, {SE.usd(w5['under'])} under its best" + (f" (STOP since {w5['since']})" if w5["stop"] else ""))
    out = head + " · " + " · ".join(parts)
    if g["verdict"] == "STOP":
        out += " · starts again when the shadow eval passes"
    return out + " (display only, never buys)"


def public_line(g: dict) -> str:
    """The line for the PUBLIC status topic (red team #19): OK / STOP + LIT's R, never the owner's $ (those stay in line(),
    read only by the private 16:15 summary / morning brief)."""
    w3, w5 = g["w3"], g["w5"]
    head = "Buy gate: OK to buy new evals" if g["verdict"] == "OK" else "Buy gate: STOP buying new evals"
    parts = []
    if "W3" in g["rules"]:
        parts.append(f"LIT last {w3['n']} trades {w3['sum40']:+.1f}R" + (" (STOP)" if w3["stop"] else ""))
    if "W5" in g["rules"]:
        parts.append("payouts-minus-fees rule " + ("STOP" if w5["stop"] else "OK"))
    return head + " · " + " · ".join(parts) + " (display only)"


def refresh(now=None, write=True, **paths) -> dict:
    sh = SE.refresh(now=now, report_path=paths.get("report_path"), state_path=paths.get("shadow_state"),
                    out_path=paths.get("shadow_out"), write=write)
    cfg = SE._read(paths.get("switch") or SWITCH, {}) or {}
    rules = tuple(r for r in (cfg.get("rules") or RULES) if r in RULES) or RULES
    today = SE.today_et(now)
    start = sh["start"]
    g = evaluate(lit_r(paths.get("seed_path"), paths.get("report_path")),
                 biz_by_day(paths.get("ledger_path"), paths.get("buys_path"), start, paths.get("trackers")), sh.get("passes") or [],
                 start, today, rules)
    g.update(t=int(now if now is not None else time.time()), start=start, shown=bool(cfg.get("show")), line=line(g), pub=public_line(g),
             shadow=sh.get("line"))
    if write:
        SE._write(paths.get("out_path") or OUT, g)
    return g


def tiny(g: dict | None = None) -> dict | None:
    """The PC report's "bg" block (< 400 bytes), only when the switch shows it."""
    g = g if g is not None else SE._read(OUT, None)
    if not isinstance(g, dict) or not g.get("shown"):
        return None
    # red team 2026-11-26: cut by UTF-8 BYTES ("·" is 2), so the block really stays < 400 B in the ext post (it was up to ~420)
    cut = lambda s, n: str(s or "").encode("utf-8")[:n].decode("utf-8", "ignore")
    if g.get("verdict") not in ("OK", "STOP"):
        return None                                      # an unknown / damaged verdict shows nothing (never a stray "OK to buy")
    return {"s": g["verdict"], "l": cut(g.get("pub"), 170), "sh": cut(g.get("shadow"), 170), "t": g.get("t")}   # pub: no owner $


def record_buy(plan: str, price: float, day: str | None = None, path: str | None = None) -> dict:
    p = path or BUYS
    L = SE._read(p, {}) or {}
    rows = list(L.get("rows") or [])
    day = day or SE.today_et()
    dt.date.fromisoformat(day)
    rows.append({"day": day, "plan": str(plan)[:40], "price": round(float(price), 2), "t": int(time.time())})
    L["rows"] = rows[-400:]
    SE._write(p, L)
    return {"ok": True, "say": f"Recorded the {plan} eval bought for {SE.usd(price)} on {day} (the buy gate counts it)."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="show")
    ap.add_argument("--plan", default="")
    ap.add_argument("--price", type=float, default=0.0)
    ap.add_argument("--day", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "buy":
        if not a.plan or a.price <= 0:
            print("give --plan and --price"); return 2
        print(record_buy(a.plan, a.price, a.day)["say"]); return 0
    g = refresh(write=False)
    print(g["line"]); print(g["shadow"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
