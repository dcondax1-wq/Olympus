"""TRADE WATCH (night team C, 2026-11-16): each live Zlarior trade next to what its backtest twin did on the same bars, and a
phone push ONLY on a real mismatch. Read-only: it builds nothing new, it reads what the bot server already computes.

Reused, not rebuilt:
  engine/fill_audit.py   the twin replay (engine/lit_live.run on the same bars) -> logs/exec_audit/report.json rows
                         (matched / missed / extra), refreshed by the server's EXEC_AUDIT watcher after every routed exit and
                         after 16:05 ET. Its own alert_payloads() picks "slipped > 4 ticks" and "missed while the PC was on";
                         its session_alerts() list of held-back / refused entries is in the same rows after the replay.
  tools/fill_check.py    the real NinjaTrader fill vs the plan (wrong size, no stop at NinjaTrader, refused entry): already a
                         push of tools/pc_report.py ("fill:" keys), so it is not repeated here.
What this adds: the twin mismatches reach the phone over the free ntfy alert topic of tools/pc_report.py (the engine's own Web
Push needs the GitHub-held key, which GitHub-free mode cannot refresh), plus two stop checks the twin makes possible:
  missed     the backtest twin entered, the bot did not, while the PC bot was running (fill_audit's reason in the text)
  slip       a fill more than 4 ticks worse than the twin (fill_audit's own rule and text)
  stop       a matched trade with no stop in the bot's ledger, or its stop more than STOP_TICKS away from the twin's (the stop
             rule is mechanical: 1 tick beyond the sweep extreme, so live and twin must agree)
Never pushed: a qty difference against the twin (the sizer's choice: eval room / weekly stop; a real size error is fill_check's
"size" flag), an "extra" trade (feed revision / restart noise, listed on the dashboard), anything older than 2 days.

  flags(root, now) -> [{"key", "t", "title", "body", "code", "entry_t"}]   (tools/pc_report.py sends each once, high priority)
  python tools/trade_watch.py            print the current flags (sends nothing)
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

STOP_TICKS = 4.0
MAX_AGE_S = 2 * 86400


def _rows(root: str) -> list:
    try:
        with open(os.path.join(root, "logs", "exec_audit", "report.json"), "r", encoding="utf-8") as fh:
            rep = json.load(fh)
        rows = rep.get("rows") if isinstance(rep, dict) else None
        return [r for r in rows if isinstance(r, dict) and r.get("entry_t")] if isinstance(rows, list) else []
    except Exception:
        return []


def _hm(t) -> str:
    try:
        from engine.fill_audit import _hm as hm
        return hm(int(t))
    except Exception:
        return time.strftime("%H:%M", time.gmtime(int(t)))


def flags(root: str = ROOT, now=None) -> list:
    """The real mismatches between the live Zlarior trades and the backtest twin. Never raises."""
    now = int(now or time.time())
    rows = _rows(root)
    out = []
    try:
        from engine import fill_audit as fa
        for p in fa.alert_payloads(rows, now):            # slip > 4 ticks + missed while the PC was on (fill_audit's rules)
            code = "missed" if ":miss:" in str(p.get("key")) else "slip"
            et_ = int(str(p.get("key")).rsplit(":", 1)[-1]) if str(p.get("key")).rsplit(":", 1)[-1].isdigit() else int(p.get("t") or now)
            out.append({"key": f"watch:lit:{et_}:{code}", "t": int(p.get("t") or et_), "code": code, "entry_t": et_,
                        "title": "Zlarior vs backtest: " + str(p.get("title") or code), "body": str(p.get("body") or "")})
    except Exception:
        pass
    for r in rows:
        try:
            if r.get("status") != "matched":
                continue
            et_ = int(r["entry_t"])
            t = int(r.get("exit_t") or et_)
            if now - t > MAX_AGE_S or t > now + 60:
                continue
            side = str(r.get("side") or "")
            if r.get("live_stop") is None and r.get("bt_stop") is not None:
                body = (f"{side} {_hm(et_)} ET: the bot's ledger has no stop for this trade; the backtest's stop was {r['bt_stop']}. "
                        "Check NinjaTrader for a working stop now.")
            elif abs(float(r.get("stop_diff_ticks") or 0)) > STOP_TICKS:
                d = float(r["stop_diff_ticks"])
                body = (f"{side} {_hm(et_)} ET: the live stop {r.get('live_stop')} sits {abs(d):.0f} ticks "
                        f"{'closer than' if d > 0 else 'farther than'} the backtest's {r.get('bt_stop')} (rule: 1 tick beyond the sweep).")
            else:
                continue
            out.append({"key": f"watch:lit:{et_}:stop", "t": t, "code": "stop", "entry_t": et_,
                        "title": "Zlarior vs backtest: stop", "body": body})
        except Exception:
            continue
    seen, uniq = set(), []
    for f in out:
        if f["key"] not in seen:
            seen.add(f["key"]); uniq.append(f)
    return uniq


if __name__ == "__main__":
    fl = flags()
    print(f"trade watch: {len(fl)} mismatch(es) vs the backtest twin")
    for f in fl:
        print(f"  {f['title']}: {f['body']}")
