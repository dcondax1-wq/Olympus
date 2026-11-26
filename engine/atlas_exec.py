"""ATLAS fast lane (big-atlasfill 2026-11-26, research/writeups/atlasfill-2026-11-26.md). BUILT, OFF BY DEFAULT, Sim accounts only.

Why: ATLAS's 4 real fills gave away 9-21 ticks (mean 14) vs the model, all in the trade's own direction, 3-5 s after the 5m bar
opened: the price runs in those seconds (other bar-close traders), not our size. Today ATLAS's entry leaves LAST in the poll: the
poll wakes at the minute + 2 s (engine/fast_entry, OFF, wakes on NinjaTrader's first tick instead), then LIT routes, the state
saves, then account C, the Rapid BLITZ, the ES learning refresh, the Brain and the second route run, and only then account B
(ATLAS). The fast lane runs account B's poll right after LIT's routing on a 5m close, before that read-only work. Same bars, same
decision (a poll is a pure function of the bars), same order: only earlier. Backtest scenario (research/atlasfill/entries.py X1):
4 s -> ~1.5 s cuts the give-away from ~11.6 to ~7.2 ticks in 2026 (not provable on bars: the Sim101 week measures it).

Switch (any one; absent everywhere = OFF = exactly today's order):
  env LE_ATLAS_EXEC=1 | data/atlas_exec.json {"on": true}      python -X utf8 -m engine.atlas_exec --on | --off | --status
PAPER_ONLY: refused for any account whose name does not start with "Sim" (a real account keeps today's order), even when ON.

The lead wires two lines in engine/live.py (not done here; research/handoff/2026-11-26/big-atlasfill/LEAD_WIRES.md):
  right after LIT's routing + the state save:   atlas_exec.early(self, df_full, df1, sym, now)
  the existing call becomes:                    if not atlas_exec.done(self, now): self._account_b_tick(df_full, df1, sym, now)

Fill rows (the zeroerr helper's names, one JSON line each, logs/atlas_exec_fills.jsonl):
  lane, side, qty, intended, filled, ticks, order_type, signal_t, send_t, ack_t, fill_t   (+ day, member, account)
Tests: python -X utf8 -m tests.test_atlas_exec
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "atlas_exec.json")
LOG = os.path.join(ROOT, "logs", "atlas_exec_fills.jsonl")
WINDOW_S = 20                    # only in the first 20 s after a 5m boundary (ATLAS enters at the 5m open)
TICK = 0.25
FIELDS = ("lane", "side", "qty", "intended", "filled", "ticks", "order_type", "signal_t", "send_t", "ack_t", "fill_t")
_C = {"t": 0.0, "on": False}


def is_on(path: str | None = None) -> bool:
    """env LE_ATLAS_EXEC=1 or data/atlas_exec.json {"on": true} (re-read at most every 30 s). Never raises."""
    if os.environ.get("LE_ATLAS_EXEC", "").strip() == "1":
        return True
    p = path or PATH
    if path is None and time.time() - _C["t"] < 30:
        return _C["on"]
    on = False
    try:
        with open(p, encoding="utf-8") as fh:
            on = (json.load(fh) or {}).get("on") is True
    except (OSError, ValueError):
        on = False
    if path is None:
        _C.update(t=time.time(), on=on)
    return on


def set_on(on: bool, path: str | None = None) -> dict:
    p = path or PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    blk = {"on": bool(on), "saved_at": int(time.time()), "note": "engine/atlas_exec.py: ATLAS's entry right after LIT's routing (Sim only)"}
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(blk, fh, indent=1)
    _C["t"] = 0.0
    return blk


def sim_only(account) -> bool:
    return isinstance(account, str) and account.startswith("Sim")


def account_of(bot) -> str | None:
    ab = getattr(bot, "acct_b", None)
    if ab is None:
        return None
    try:
        return ab.adapter_cfg().get("nt_account")
    except Exception:
        return getattr(ab, "name", None)


def at_5m_open(now) -> bool:
    return int(now) % 300 < WINDOW_S


def early(bot, df5, df1, sym, now, path: str | None = None) -> str:
    """Run account B's poll now (right after LIT) when ON, on a Sim account, in the first seconds of a 5m bar.
    Returns what it did: 'off' | 'not 5m open' | 'no account B' | 'refused: <account> is not Sim' | 'ran'. Never raises."""
    try:
        if not is_on(path):
            return "off"
        if not at_5m_open(now):
            return "not 5m open"
        acct = account_of(bot)
        if acct is None:
            return "no account B"
        if not sim_only(acct):
            return f"refused: {acct} is not Sim"
        for ra in (bot._rapid_atlases() if callable(getattr(bot, "_rapid_atlases", None)) else []):
            ra_acct = account_of(type("B", (), {"acct_b": ra})())
            if not sim_only(ra_acct):                    # _account_b_tick also runs the Rapid ATLAS lanes: all must be Sim
                return f"refused: Rapid ATLAS {ra_acct} is not Sim"
        bot._atlas_exec_done = int(now) - int(now) % 60
        bot._account_b_tick(df5, df1, sym, now)
        return "ran"
    except Exception as e:  # noqa: BLE001
        try:
            bot._note_error(f"atlas_exec early lane failed: {e.__class__.__name__}: {e}")
        except Exception:
            pass
        return f"error {e.__class__.__name__}"


def done(bot, now) -> bool:
    """True when the early lane already ran account B in this minute (the regular call then skips: one poll per minute)."""
    return getattr(bot, "_atlas_exec_done", None) == int(now) - int(now) % 60


def fill_row(lane, side, qty, intended, filled, order_type="MARKET", signal_t=None, send_t=None, ack_t=None, fill_t=None,
             **extra) -> dict:
    d = 1 if str(side).lower() in ("buy", "long", "1") else -1
    ticks = None if filled is None or intended is None else round((float(filled) - float(intended)) * d / TICK, 2)
    row = {"lane": lane, "side": "buy" if d == 1 else "sell", "qty": int(qty), "intended": intended, "filled": filled, "ticks": ticks,
           "order_type": order_type, "signal_t": signal_t, "send_t": send_t, "ack_t": ack_t, "fill_t": fill_t}
    row.update(extra)
    return row


def log_fill(row: dict, path: str | None = None) -> None:
    p = path or LOG
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=float) + "\n")
    except OSError:
        pass


def from_ledger(path_glob: str | None = None) -> list:
    """Back-fill rows from the PC day folders' live ATLAS / LIT entries (signal_t = the bar open, ack_t = the ledger time;
    send_t and fill_t are not recorded yet: None)."""
    import glob
    import gzip
    out = []
    for p in sorted(glob.glob(path_glob or os.path.join(ROOT, "data", "pc_days", "*", "trades.jsonl.gz"))):
        for r in (json.loads(x) for x in gzip.open(p, "rt")):
            if r.get("side") not in ("buy", "sell") or r.get("mode") != "live":
                continue
            fp = [lg.get("fill_px") for lg in ((r.get("result") or {}).get("legs") or []) if lg.get("fill_px")]
            if not fp:
                continue
            out.append(fill_row("atlas" if r.get("bot") == "atlas" else "lit", r["side"], r.get("qty") or 1, r.get("entry"),
                                sum(fp) / len(fp), signal_t=r.get("entry_t"), ack_t=r.get("t"),
                                day=os.path.basename(os.path.dirname(p)), member=r.get("strategy", "")))
    return out


def summary(rows: list) -> dict:
    out = {}
    for lane in sorted({r["lane"] for r in rows}):
        R = [r for r in rows if r["lane"] == lane and r.get("ticks") is not None]
        if not R:
            continue
        t = sorted(r["ticks"] for r in R)
        lat = [r["ack_t"] - r["signal_t"] for r in R if r.get("ack_t") and r.get("signal_t")]
        out[lane] = {"n": len(R), "mean_ticks": round(sum(t) / len(t), 2), "median_ticks": (t[len(t) // 2] if len(t) % 2 else (t[len(t) // 2 - 1] + t[len(t) // 2]) / 2),
                     "mean_signal_to_ack_s": round(sum(lat) / len(lat), 2) if lat else None,
                     "decision": ("enough fills to re-calibrate (research/atlasfill/entries.py)" if len(R) >= 10 else
                                  f"{10 - len(R)} more fills before re-calibrating")}
    return out


def main(argv=None):
    a = list(argv if argv is not None else sys.argv[1:])
    if "--on" in a:
        print(set_on(True))
    elif "--off" in a:
        print(set_on(False))
    elif "--report" in a:
        rows = from_ledger()
        if os.path.exists(LOG):
            rows += [json.loads(x) for x in open(LOG, encoding="utf-8") if x.strip()]
        print(json.dumps(summary(rows), indent=1))
    else:
        print(json.dumps({"on": is_on(), "file": PATH, "window_s": WINDOW_S, "paper_only": "Sim accounts only"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
