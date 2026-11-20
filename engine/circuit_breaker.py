"""ZEUS circuit breaker (night-risk 2026-11-18, docs/ZEUS_FEATURES.md #14): is a live strategy falling behind its own backtest twin?

ADVICE ONLY. It never sizes, pauses, routes, cancels or arms anything and never touches live_model*.json (turning the old
equity filter on is a strategy change: engine/equity_filter.py stays OFF). It reads files the bot already writes and, when the
live trades of Zlarior (LIT) or ATLAS run several R worse than the backtest twin on the same bars, it posts ONE Board event and
ONE phone push (via tools/pc_report.py, type account_status) with a recommendation the owner acts on himself:

  OK         the live trades match the twin (a losing streak the twin also had is normal variance, not a broken bot)
  WATCH      gap <= -WATCH_R over the last N trades: Board line only, no push
  SIZE DOWN  gap <= -SIZE_DOWN_R: "trade half size until the gap is explained" (push)
  PAUSE      gap <= -PAUSE_R: "pause this strategy (phone /safety/ PAUSE) and check NinjaTrader + the bot log" (push)
  back       the gap recovers above -BACK_R after a push: one "back to normal" Board line (no push)

gap = sum over the last N (WINDOW) closed live trades of (live R - twin R), each trade clipped to +-CLIP_R so a single feed-revision
freak cannot trip PAUSE alone; R = the trade's $ / its own risk $ (entry to stop x $2 a point x micros). The $ gap is shown first.
Missed trades (twin traded, bot did not, PC on) lose no money and are counted, not added to the gap (fill_audit / trade_watch
already push them).

Sources (read-only):
  Zlarior   logs/exec_audit/report.json rows (engine/fill_audit: matched = live P&L vs the twin at the live micros; extra = a trade
            the twin did not take, twin R 0)
  ATLAS     data/live_state_acctb.json ledger (entries + exits with $) vs logs/exec_audit/atlas_twin.json (tools/trade_watch's twin)
State: logs/risk/breaker.json (gitignored): the pairs seen (so the window outlives the 2-day caches) + the last level per bot.

  python -X utf8 -m engine.circuit_breaker            # print each strategy's gap + recommendation (sends nothing)
  flags(root, now) -> [push dicts]                    # tools/pc_report.py, every run; keys "breaker:<bot>:<level>:<entry_t>"
Switch: LE_BREAKER=0 = off (no Board line, no push). Tests: tests/test_risk_monitors.py.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PV = 2.0                       # MNQ $ a point a micro
COMM = 1.90
WINDOW = 10                    # last N closed live trades per strategy
MIN_N = 3                      # fewer pairs = no verdict
CLIP_R = 2.0                   # one trade's gap counts at most +-2R
WATCH_R, SIZE_DOWN_R, PAUSE_R, BACK_R = 2.0, 3.0, 5.0, 1.5
KEEP_PAIRS = 60
BOTS = ("zlarior", "atlas")
NAMES = {"zlarior": "Zlarior", "atlas": "ATLAS"}
LEVELS = ("ok", "watch", "size_down", "pause")
SAY = {"ok": "OK", "watch": "WATCH", "size_down": "SIZE DOWN", "pause": "PAUSE"}
ADVICE = {"ok": "live = backtest: nothing to do.",
          "watch": "watching: no action yet.",
          "size_down": "recommend HALF size until the gap is explained (check slippage, stops and the bot log).",
          "pause": "recommend PAUSE for this strategy (phone /safety/ PAUSE) and check NinjaTrader + the bot log before the next trade."}


def _f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"))
        from .fsutil import replace
        replace(tmp, path)
    except Exception:
        pass


def usd(v) -> str:
    v = round(float(v or 0))
    return "$0" if v == 0 else f"{'+' if v > 0 else '-'}${abs(v):,.0f}"


def _clip(x):
    return max(-CLIP_R, min(CLIP_R, x))


# ------------------------------------------------------------------------------------------------ pairs (live vs twin)
def lit_pairs(root: str = ROOT) -> tuple:
    """Zlarior: ([pair], missed_pc_on) from engine/fill_audit's report.json. pair = {t, entry_t, live_r, twin_r, gap_usd}."""
    rep = _read(os.path.join(root, "logs", "exec_audit", "report.json"), {})
    rows = rep.get("rows") if isinstance(rep, dict) else None
    rows = [r for r in rows if isinstance(r, dict) and r.get("entry_t")] if isinstance(rows, list) else []
    out, extras, risks, missed = [], [], [], 0
    for r in rows:
        st = r.get("status")
        if st == "missed":
            missed += 1 if r.get("pc_on") else 0
            continue
        lp = _f(r.get("live_pnl"))
        if lp is None:
            continue                                     # still open / exit not priced
        t = int(_f(r.get("exit_t")) or _f(r.get("entry_t")) or 0)
        if st == "matched":
            q = int(_f(r.get("live_qty")) or 0)
            e, s, bq = _f(r.get("bt_entry")), _f(r.get("bt_stop")), _f(r.get("bt_pnl_live_qty"))
            if not q or e is None or s is None or bq is None or abs(e - s) <= 0:
                continue
            risk = abs(e - s) * PV * q
            risks.append(risk)
            out.append({"t": t, "entry_t": int(r["entry_t"]), "live_r": round(lp / risk, 3), "twin_r": round(bq / risk, 3),
                        "gap_usd": round(lp - bq, 2)})
        elif st == "extra":
            extras.append((t, int(r["entry_t"]), lp))
    if extras and risks:                                 # an extra trade has no twin stop: R at the median matched risk
        med = sorted(risks)[len(risks) // 2]
        for t, et_, lp in extras:
            out.append({"t": t, "entry_t": et_, "live_r": round(lp / med, 3), "twin_r": 0.0, "gap_usd": round(lp, 2), "extra": True})
    return out, missed


def _fill(row):
    res = row.get("result") if isinstance(row.get("result"), dict) else {}
    px = [(float(lg["fill_px"]), int(lg.get("filled") or 0)) for lg in res.get("legs") or []
          if isinstance(lg, dict) and lg.get("fill_px") is not None and int(lg.get("filled") or 0) > 0]
    n = sum(q for _, q in px)
    return sum(p * q for p, q in px) / n if n else None


def atlas_pairs(root: str = ROOT) -> tuple:
    """ATLAS: ([pair], 0) from account B's ledger vs tools/trade_watch's twin cache (twin trades carry "r" since night-risk)."""
    st = _read(os.path.join(root, "data", "live_state_acctb.json"), {})
    tw = _read(os.path.join(root, "logs", "exec_audit", "atlas_twin.json"), {})
    if not isinstance(st, dict) or not isinstance(tw, dict):
        return [], 0
    twin = {}
    for day, c in tw.items():
        for t in (c.get("trades") if isinstance(c, dict) else None) or []:
            if isinstance(t, dict) and t.get("entry_t") is not None:
                twin.setdefault(int(t["entry_t"]), []).append(t)
    out = _atlas_ledger_pairs([r for r in st.get("ledger") or [] if isinstance(r, dict)], tw, twin)
    # ATLAS + Zlarior on ONE account (engine/combo50k.py, OFF by default): ATLAS's trades on Zlarior's 50K count for ATLAS
    z = _read(os.path.join(root, "data", "live_state.json"), {})
    zl = [r for r in (z.get("ledger") if isinstance(z, dict) else None) or [] if isinstance(r, dict) and r.get("combo")]
    if zl:
        out += _atlas_ledger_pairs(zl, tw, twin)
    return out, 0


def _atlas_ledger_pairs(ledger: list, tw: dict, twin: dict) -> list:
    """One account's ATLAS ledger rows -> pairs vs the twin (account B's 25K, or ATLAS's combo rows on the 50K)."""
    entries, out = {}, []
    for r in ledger:
        if r.get("side") in ("buy", "sell") and r.get("entry_t") is not None and (r.get("result") or {}).get("ok") is not False:
            entries[int(r["entry_t"])] = r
    seen = set()
    for r in ledger:
        if r.get("side") != "exit" or r.get("entry_t") is None or str(r.get("reason") or "").upper() in ("NO TRADE", "KILL SWITCH"):
            continue
        et_, pnl = int(r["entry_t"]), _f(r.get("pnl"))
        e = entries.get(et_)
        if pnl is None or e is None or et_ in seen:
            continue
        seen.add(et_)
        d = 1 if e.get("side") == "buy" else -1
        q = int(_f(e.get("qty")) or 0)
        px, stop = _fill(e) or _f(e.get("entry")), _f(e.get("stop"))
        if not q or px is None or stop is None or abs(px - stop) <= 0:
            continue
        risk = abs(px - stop) * PV * q
        cand = [x for x in twin.get(et_, []) if int(x.get("dir") or 0) == d]
        tm = next((x for x in cand if x.get("key") == e.get("src")), None) or (cand[0] if cand else None)
        t = int(_f(r.get("exit_t")) or _f(r.get("t")) or et_)
        if tm is None:
            from .account_b import trading_day
            if trading_day(et_) not in tw:
                continue                                 # no twin for that day: no verdict on it
            out.append({"t": t, "entry_t": et_, "live_r": round(pnl / risk, 3), "twin_r": 0.0, "gap_usd": round(pnl, 2), "extra": True})
            continue
        tr = _f(tm.get("r"))
        if tr is None or str(tm.get("exit_kind") or "").upper() == "OPEN":
            continue                                     # an old cache row without R, or the twin still open
        out.append({"t": t, "entry_t": et_, "live_r": round(pnl / risk, 3), "twin_r": round(tr, 3),
                    "gap_usd": round(pnl - tr * risk, 2)})
    return out


# ------------------------------------------------------------------------------------------------ verdict
def verdict(pairs: list, missed: int = 0, n: int = WINDOW) -> dict:
    last = sorted(pairs, key=lambda p: (p["t"], p["entry_t"]))[-n:]
    gap = round(sum(_clip(p["live_r"] - p["twin_r"]) for p in last), 2)
    out = {"n": len(last), "gap_r": gap, "gap_usd": round(sum(p["gap_usd"] for p in last), 2),
           "live_r": round(sum(p["live_r"] for p in last), 2), "twin_r": round(sum(p["twin_r"] for p in last), 2),
           "missed": int(missed), "newest": last[-1]["entry_t"] if last else None}
    if len(last) < MIN_N:
        out["level"] = "ok"
        out["note"] = f"only {len(last)} trade(s) to compare (needs {MIN_N})"
        return out
    out["level"] = "pause" if gap <= -PAUSE_R else "size_down" if gap <= -SIZE_DOWN_R else "watch" if gap <= -WATCH_R else "ok"
    return out


def text(bot: str, v: dict) -> tuple:
    nm = NAMES.get(bot, bot)
    title = f"ZEUS breaker: {nm} {SAY[v['level']]}"
    body = (f"{nm} live is {usd(v['gap_usd'])} ({v['gap_r']:+.1f}R) vs its backtest twin over the last {v['n']} trades "
            f"(live {v['live_r']:+.1f}R, twin {v['twin_r']:+.1f}R). " + ADVICE[v["level"]])
    if v.get("missed"):
        body += f" Also {v['missed']} twin trade(s) missed while the PC was on."
    return title, body + " Advice only: ZEUS changed nothing."


def status(root: str = ROOT) -> dict:
    """{bot: verdict} from the files plus the stored pairs (read-only, writes nothing)."""
    S = _read(os.path.join(root, "logs", "risk", "breaker.json"), {})
    S = S if isinstance(S, dict) else {}
    out = {}
    for bot, fn in (("zlarior", lit_pairs), ("atlas", atlas_pairs)):
        try:
            new, missed = fn(root)
        except Exception:
            new, missed = [], 0
        have = {int(p["entry_t"]): p for p in (S.get("pairs") or {}).get(bot) or [] if isinstance(p, dict) and p.get("entry_t")}
        for p in new:
            have[int(p["entry_t"])] = p                  # the newest replay wins
        out[bot] = {"pairs": sorted(have.values(), key=lambda p: (p["t"], p["entry_t"]))[-KEEP_PAIRS:], "missed": missed}
        out[bot]["v"] = verdict(out[bot]["pairs"], missed)
    return out


def flags(root: str = ROOT, now=None, emit=None) -> list:
    """tools/pc_report.py's hook: update logs/risk/breaker.json, post a Board event on each level change, and return the phone
    pushes (only SIZE DOWN / PAUSE, once per level per newest trade). emit(kind, acct, text, data) for tests. Never raises."""
    if os.environ.get("LE_BREAKER", "1").strip() == "0":
        return []
    try:
        return _flags(root, int(now or time.time()), emit)
    except Exception:
        return []


def _flags(root, now, emit):
    if emit is None:
        if os.path.abspath(root) == os.path.abspath(ROOT):
            from .board_events import emit
        else:
            emit = lambda *a, **k: None                  # a test's fake root never writes the real Board
    path = os.path.join(root, "logs", "risk", "breaker.json")
    S = _read(path, {})
    S = S if isinstance(S, dict) else {}
    lv = dict(S.get("level") or {})
    cur = status(root)
    pushes = []
    for bot in BOTS:
        v = cur[bot]["v"]
        was = lv.get(bot, "ok")
        new = v["level"]
        if new == "ok" and was != "ok" and v["gap_r"] <= -BACK_R:
            new = "watch" if was in ("size_down", "pause") else "ok"    # hysteresis: back only once the gap is above -BACK_R
        if new != was:
            title, body = text(bot, {**v, "level": new})
            if new == "ok":
                title, body = f"ZEUS breaker: {NAMES[bot]} back to normal", (f"{NAMES[bot]} live is back in line with its backtest "
                                                                              f"twin ({usd(v['gap_usd'])}, {v['gap_r']:+.1f}R over "
                                                                              f"{v['n']} trades).")
            try:
                emit("risk_alert", bot, f"{title}. {body}"[:300],
                     {"what": "breaker", "level": new, "gap_r": v["gap_r"], "gap_usd": v["gap_usd"], "n": v["n"]})
            except Exception:
                pass
            if LEVELS.index(new) >= LEVELS.index("size_down") and LEVELS.index(new) > LEVELS.index(was if was in LEVELS else "ok"):
                pushes.append({"key": f"breaker:{bot}:{new}:{v['newest']}", "t": now, "title": title, "body": body,
                               "code": new, "entry_t": v["newest"]})
            lv[bot] = new
    _write(path, {"t": now, "level": lv, "pairs": {b: cur[b]["pairs"] for b in BOTS},
                  "v": {b: cur[b]["v"] for b in BOTS}})
    return pushes


def main(argv=None) -> int:
    cur = status()
    for bot in BOTS:
        v = cur[bot]["v"]
        print(f"{NAMES[bot]:8s} {SAY[v['level']]:9s} gap {usd(v['gap_usd'])} ({v['gap_r']:+.2f}R) over {v['n']} trades; "
              f"live {v['live_r']:+.2f}R, twin {v['twin_r']:+.2f}R" + (f"; {v['note']}" if v.get("note") else ""))
    print("Advice only: nothing here changes a bot, a size or an order.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
