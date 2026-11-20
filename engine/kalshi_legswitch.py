"""K8 per-leg OFF / ON from the leg's own rolling record (day-kalshi 2026-11-20; rule fixed in research/kalshi_k8_day/PREREG_legswitch.md
before it was tested). Pure: no file is written, no order, no network.

For each leg: its last 20 settled windows (every weekday window, bet or not; the bot's paper ledger records them all).
  pause  when it won 10 or fewer of the last 20 (<= 50%, under the ~54% break-even)
  resume when it won 12 or more of the last 20 (>= 60%); 11 = keep the current state; under 20 windows = never paused.
It may only pause / resume a leg the owner armed. Whether the live bot OBEYS it is LIVE_ON below: the walk-forward test decides
(research/kalshi_k8_day/legswitch.py -> legswitch.json). OFF = display only (the phone shows the record and what it would do).
"""
from __future__ import annotations

RULE = {"n": 20, "pause_at": 10, "resume_at": 12}
LIVE_ON = False          # set by the pre-registered walk-forward verdict (legswitch.json): see research/handoff/2026-11-20/kalshi/REPORT.md


def decide(results, paused=False, rule=None) -> dict:
    """results = 1 (won) / 0 (lost) of the leg's settled windows, oldest first; paused = the state before.
    -> {"paused", "won", "of", "why"}: the state after reading the last n windows."""
    r = rule or RULE
    last = [1 if x else 0 for x in (results or [])][-r["n"]:]
    won, of = sum(last), len(last)
    if of < r["n"]:
        return {"paused": False, "won": won, "of": of, "why": f"{of} of {r['n']} windows so far"}
    if won <= r["pause_at"]:
        paused = True
    elif won >= r["resume_at"]:
        paused = False
    why = (f"won {won} of the last {of} (resumes at {r['resume_at']})" if paused
           else f"won {won} of the last {of} (pauses at {r['pause_at']})")
    return {"paused": paused, "won": won, "of": of, "why": why}


def replay(results, rule=None) -> dict:
    """The state today when the rule has run every day over the whole record (the hysteresis needs the path, not only the last 20)."""
    paused, out = False, {"paused": False, "won": 0, "of": 0, "why": ""}
    res = [1 if x else 0 for x in (results or [])]
    for i in range(len(res) + 1):
        out = decide(res[:i], paused, rule)
        paused = out["paused"]
    return out


def leg_results(paper_rows, lid) -> list:
    """The leg's settled windows from the bot's paper ledger, oldest first (1 won / 0 lost); skipped windows (no fill) count too
    when Kalshi's result is known (status 'skip' rows carry no result: left out)."""
    rs = [r for r in paper_rows if r.get("leg") == lid and r.get("result") in ("won", "lost")]
    rs.sort(key=lambda r: float(r.get("open_t") or 0))
    seen, out = set(), []
    for r in rs:
        if r.get("day") in seen:
            continue
        seen.add(r.get("day"))
        out.append(1 if r["result"] == "won" else 0)
    return out


def states(paper_rows, legs, rule=None) -> dict:
    """{leg id: decide()} for the legs, from the paper ledger."""
    return {lid: replay(leg_results(paper_rows, lid), rule) for lid in legs}
