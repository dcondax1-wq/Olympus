"""FEED FILLS (night-botgap 2026-11-18, research/writeups/bot-gap-2026-11-18.md). Wired by the lead into tools/pc_report.full() (ext "fq").
the 23:00 ET cut-off for PC code, so the lead reviews it and moves it to engine/feed_fills.py (git mv) before wiring it. Nothing imports
it from here except tests/test_journal_edge.py (part d: the block it makes is the one journal/edgecore.js fills() reads).
The small "fills vs plan" block the PC can add to its
ntfy "le-live-ext" post (ext key "fq"), so the phone's journal page (tools/web_public/journal/edge.html, "Fills vs plan") shows what the
PC already checks on every trade. Today those checks only reach the owner as a push when something is wrong; the phone's old Execution
page read them from the GitHub heartbeat, which is gone. Read only: it never trades, arms, routes or sizes, never raises, stdlib only.

compact(exec_block, reviews, now) -> {"t", "ex": {...}, "fc": [[...], ...]} or None (nothing to say)
  ex  engine/fill_audit.heartbeat_block() (the heartbeat's "exec": Zlarior's live trades against the LIT backtest on the same bars,
      45 days): fr / to (days), n matched trades, sl slippage $, ex execution $, mi missed backtest trades (mo of them while the PC was
      on, mu the $ the backtest made on them), xt extra trades (xu their $), es / xs median entry / exit slippage in ticks, la median
      latency s, sp trades over the alert, m = the last 3 months [[YYYY-MM, trades, slip $, exec $, missed, missed $]]
  fc  tools/fill_check.reviews() (every real NinjaTrader fill of the last 36 hours, newest first, at most N_CHECKS):
      [acct, entry_t, dir, plan micros, filled micros, entry slip ticks, exit slip ticks, execution $, "flag codes", "L" live | "S" Sim]
      acct = the bot key (lit / atlas); BLITZ is hidden (owner 2026-11-15) and never sent; no account name or number is in it.
~300-600 bytes. cut(fq, n) keeps the newest n checks (pc_report's size cuts). Tests: python -X utf8 -m tests.test_journal_edge (part d).

Wiring (the lead; tools/pc_report.py full(), next to the "at" block):
    try:
        from engine import feed_fills
        fq = feed_fills.compact(hb.get("exec"), snap.get("fills"), snap.get("t"))
        if fq:
            out["fq"] = fq
    except Exception:  # noqa: BLE001
        pass
  + "fq" in EXT_ORDER (after "at") and _cuts "fq": [lambda v: feed_fills.cut(v, 2), lambda v: feed_fills.cut(v, 0)].
"""
from __future__ import annotations

N_CHECKS = 4
HIDDEN = ("blitz", "acctc", "acct_c")


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _f(v, nd=2):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if x == x and abs(x) != float("inf") else None


def _i(v):
    x = _f(v, 6)
    return None if x is None else int(round(x))


def _s(v, n=10):
    return str(v)[:n] if isinstance(v, str) and v.strip() else None


def _audit(ex) -> dict | None:
    E = _d(ex)
    if not E:
        return None
    out = {"fr": _s(E.get("from")), "to": _s(E.get("to")), "n": _i(E.get("trades")) or 0, "sl": _f(E.get("slip_usd")), "ex": _f(E.get("exec_usd")),
           "mi": _i(E.get("missed")) or 0, "mo": _i(E.get("missed_pc_on")) or 0, "mu": _f(E.get("missed_usd")), "xt": _i(E.get("extra")) or 0,
           "xu": _f(E.get("extra_usd")), "es": _f(E.get("entry_slip_ticks"), 1), "xs": _f(E.get("exit_slip_ticks"), 1), "la": _f(E.get("latency_s_med"), 1),
           "sp": _i(E.get("slipped")) or 0}
    m = []
    for x in _l(E.get("months"))[-3:]:
        x = _d(x)
        if _s(x.get("month"), 7):
            m.append([str(x["month"])[:7], _i(x.get("trades")) or 0, _f(x.get("slip_usd")), _f(x.get("exec_usd")), _i(x.get("missed")) or 0, _f(x.get("missed_usd"))])
    if m:
        out["m"] = m
    if not (out["n"] or out["mi"] or out["xt"]):
        return None
    return {k: v for k, v in out.items() if v is not None}


def _check(r) -> list | None:
    r = _d(r)
    acct = str(r.get("acct") or "").lower()
    et = _i(r.get("entry_t"))
    if not acct or not et or any(h in acct for h in HIDDEN):
        return None
    P, R, S, C = _d(r.get("plan")), _d(r.get("real")), _d(r.get("slip")), _d(r.get("costs"))
    codes = " ".join(sorted({str(_d(f).get("code"))[:12] for f in _l(r.get("flags")) if _d(f).get("code")}))
    return [acct[:12], et, -1 if _i(r.get("dir")) == -1 else 1, _i(P.get("qty")), _i(R.get("filled")), _f(S.get("entry_ticks"), 1), _f(S.get("exit_ticks"), 1),
            _f(C.get("exec_usd")), codes, "S" if str(r.get("kind") or "").upper() == "SIM" else "L"]


def compact(exec_block=None, reviews=None, now=None) -> dict | None:
    """The "fq" block. Never raises; None when there is neither an audit nor a fill check to show."""
    try:
        ex = _audit(exec_block)
        fc = []
        for r in _l(reviews):
            row = _check(r)
            if row:
                fc.append(row)
        fc.sort(key=lambda x: x[1], reverse=True)
        fc = fc[:N_CHECKS]
        if not ex and not fc:
            return None
        out = {"t": _i(now) or _i(_d(exec_block).get("t"))}
        if ex:
            out["ex"] = ex
        if fc:
            out["fc"] = fc
        return out
    except Exception:  # noqa: BLE001
        return None


def cut(fq, n: int) -> None:
    """Keep only the newest n fill checks, in place (0 = none; the audit totals stay)."""
    q = _d(fq)
    if isinstance(q.get("fc"), list):
        q["fc"] = q["fc"][:n] if n > 0 else []
        if not q["fc"]:
            q.pop("fc", None)
