"""ZEUS daily review (owner 2026-11-18: "the bot and you should constantly be learning, improving, adapting").

One short self-review a night, on the PC after the close (engine/datapipe.run) and reproducible in the cloud from the data
branch (python tools/data_pull.py --review): the SAME function reads the same day folders (days/YYYY-MM-DD/: trades, decisions,
twin, manifest). docs/DATA_PIPE.md.

It looks at
  1. live vs the backtest twin, per trade (engine/fill_audit's nightly rows): matched / missed / extra, entry + exit slippage
     in ticks and $, execution $, the backtest $ not taken; orders the broker refused (ledger rows with ok false)
  2. the edge-health light (research/lab/edge_health.json "card", tools/edge_health.py): GREEN / AMBER / RED + data date
  3. Zlarior (LIT) and ATLAS rolling stats from the closed ledger rows: last 20 trades, win %, PF, net $, trades a week,
     per account too
  4. anything odd: no entries for NO_TRADE_ACT sessions in a row (while the twin had setups), orders refused again, a backtest
     trade missed with the PC on twice in 5 sessions, entry slippage over SLIP_ACT ticks (median of the last 10), a session
     with no NinjaTrader bars, the light turning RED, the data push failing again
Output: review dict (day, text, items, stats, twin, light, proposals, action). On the PC: logs/zeus/review_<day>.json +
latest.json, ONE board event "daily_review" a day (engine/board_events.emit) and ONE phone push (the PC's private ntfy
topic, engine/learn_loop.push_phone) only when an item needs the owner (action). Strategy ideas never touch live settings:
they go to logs/zeus/research_queue.jsonl + the day folder's proposals.jsonl, and the cloud's tools/data_pull.py merges
them into research/zeus_queue.jsonl for Claude, who tests them under CLAUDE.md "Strategy changes" before anything changes.
Never trades, arms, routes, sizes or edits a setting.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "logs", "zeus")
EDGE = os.path.join(ROOT, "research", "lab", "edge_health.json")
VERSION = 1
WINDOW = 20                    # rolling trades
NO_TRADE_INFO, NO_TRADE_ACT = 3, 6
SLIP_ACT = 2.0                 # ticks, median entry slippage of the last 10 matched trades
SLIP_PROPOSE = 1.0
REJECT_ACT = 2
BOTS = ("zlarior", "atlas")
NAMES = {"zlarior": "Zlarior", "atlas": "ATLAS"}


def _f(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def usd(v) -> str:
    v = round(float(v or 0))
    return "$0" if v == 0 else f"{'+' if v > 0 else '-'}${abs(v):,.0f}"


def _md(day) -> str:
    try:
        d = dt.date.fromisoformat(day)
        return f"{d:%b} {d.day}"
    except Exception:
        return str(day)


def _med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


# ================================================================================================ pieces
def closed_trades(days: list) -> list:
    """Closed trades from the ledger rows: one per (src, entry_t) exit row with a P&L (KILL SWITCH without P&L skipped)."""
    out, seen = [], set()
    for b in days:
        for r in b.get("trades") or []:
            if r.get("side") != "exit" or str(r.get("reason") or "").upper() == "NO TRADE":
                continue
            p = _f(r.get("pnl"))
            if p is None:
                continue
            k = (r.get("src"), r.get("entry_t"), r.get("t"))
            if k in seen:
                continue
            seen.add(k)
            out.append({"day": b["day"], "bot": r.get("bot"), "acct": r.get("acct"), "mode": r.get("mode"), "pnl": p,
                        "t": r.get("exit_t") or r.get("t"), "reason": r.get("reason")})
    return sorted(out, key=lambda x: (x["day"], int(x["t"] or 0)))


def entries(day_bundle: dict) -> list:
    return [r for r in day_bundle.get("trades") or [] if r.get("side") in ("buy", "sell")]


def rejects(day_bundle: dict) -> list:
    out = []
    for r in entries(day_bundle):
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        if res.get("ok") is False:
            out.append({"bot": r.get("bot"), "acct": r.get("acct"), "t": r.get("t"), "error": str(res.get("error") or "refused")[:120]})
    return out


def stats(T: list, sessions: int) -> dict:
    if not T:
        return {"n": 0}
    w = [t["pnl"] for t in T if t["pnl"] > 0]
    l = [t["pnl"] for t in T if t["pnl"] <= 0]
    gl = -sum(l)
    return {"n": len(T), "win_pct": round(100.0 * len(w) / len(T), 1), "pf": round(sum(w) / gl, 2) if gl > 0 else None,
            "net_usd": round(sum(t["pnl"] for t in T), 2), "usd_per_trade": round(sum(t["pnl"] for t in T) / len(T), 2),
            "per_week": round(len(T) / max(1, sessions) * 5, 2) if sessions else None,
            "from": T[0]["day"], "to": T[-1]["day"]}


def rolling(days: list, n: int = WINDOW) -> dict:
    C = closed_trades(days)
    sess = [b["day"] for b in days]
    out = {}
    for bot in BOTS:
        T = [t for t in C if t["bot"] == bot]
        last = T[-n:]
        s_used = len([d for d in sess if last and d >= last[0]["day"]]) if last else len(sess)
        S = stats(last, s_used)
        S["live"] = stats([t for t in last if t["mode"] == "live"], s_used).get("net_usd") if last else None
        S["by_acct"] = {a: stats([t for t in last if t["acct"] == a], s_used) for a in sorted({t["acct"] for t in last})}
        S["today_usd"] = round(sum(t["pnl"] for t in T if t["day"] == sess[-1]), 2) if sess else 0.0
        S["today_n"] = sum(1 for t in T if sess and t["day"] == sess[-1])
        out[bot] = S
    return out


def twin_block(days: list, k: int = 10) -> dict:
    """The newest day's twin + the last k sessions' matched slippage."""
    def rows(b):
        return ((b.get("twin") or {}).get("nightly") or {}).get("rows") or []
    today = days[-1] if days else {}
    R = rows(today)
    N = (today.get("twin") or {}).get("nightly") or {}
    recent = [r for b in days[-k:] for r in rows(b)]
    M = [r for r in recent if r.get("status") == "matched"]
    return {"verdict": N.get("verdict"), "text": N.get("text"),
            "matched": sum(1 for r in R if r.get("status") == "matched"), "missed": sum(1 for r in R if r.get("status") == "missed"),
            "extra": sum(1 for r in R if r.get("status") == "extra"),
            "missed_pc_on": sum(1 for r in R if r.get("status") == "missed" and r.get("pc_on")),
            "missed_usd": round(sum(_f(r.get("missed_usd")) or 0 for r in R if r.get("status") == "missed"), 2),
            "slip_usd": round(sum(_f(r.get("slip_usd")) or 0 for r in R if r.get("status") == "matched"), 2),
            "exec_usd": round(sum(_f(r.get("exec_usd")) or 0 for r in R if r.get("status") == "matched"), 2),
            "bt_trades": sum(1 for r in R if r.get("status") != "extra"),
            "recent_n": len(M), "recent_entry_slip_med": _med([_f(r.get("entry_slip_ticks")) for r in M]),
            "recent_exit_slip_med": _med([_f(r.get("exit_slip_ticks")) for r in M]),
            "recent_miss_reasons": [str(r.get("reason") or "")[:80] for r in recent if r.get("status") == "missed" and r.get("pc_on")],
            "per_trade": [{k2: r.get(k2) for k2 in ("status", "side", "entry_t", "entry_slip_ticks", "exit_slip_ticks", "slip_usd",
                                                    "exec_usd", "bt_pnl", "live_pnl", "missed_usd", "reason")} for r in R][:12]}


def edge_light(path: str = EDGE, card: dict | None = None) -> dict:
    if card is None:
        try:
            with open(path, encoding="utf-8") as fh:
                card = (json.load(fh) or {}).get("card") or {}
        except Exception:
            card = {}
    return {"light": card.get("light"), "line": card.get("line"), "data_to": card.get("data_to"), "pf40": card.get("pf40")}


def bars_ok(b: dict) -> bool:
    files = (b.get("manifest") or {}).get("files") or {}
    return any(p.startswith("bars/") and (v.get("rows") or 0) > 0 for p, v in files.items())


# ================================================================================================ the review
def review(days: list, edge: dict | None = None, prev: dict | None = None, pipe: dict | None = None, now=None) -> dict:
    """days = the day bundles (engine/datapipe.load_day), oldest first, the reviewed day last. Pure: tests feed bundles."""
    now = int(now if now is not None else time.time())
    days = [b for b in days if b.get("day")]
    day = days[-1]["day"] if days else None
    edge = edge or {}
    items, proposals = [], []
    wk = dt.date.fromisoformat(day).isocalendar() if day else None
    wkey = f"{wk[0]}w{wk[1]:02d}" if wk else "na"

    def item(level, key, text, fix=""):
        items.append({"level": level, "key": key, "text": text, **({"fix": fix} if fix else {})})

    def propose(pid, bot, what, evidence):
        proposals.append({"id": f"{pid}-{wkey}", "day": day, "bot": bot, "what": what, "evidence": evidence,
                          "rule": "research only: test under CLAUDE.md Strategy changes (Jan-Jun pick, Jul-Oct check, 2021-25, costs) "
                                  "before any live change; never applied by the bot"})
    if not days:
        return {"v": VERSION, "day": None, "t": now, "text": "ZEUS daily review: no data yet.", "items": [], "action": False,
                "proposals": []}
    tw = twin_block(days)
    roll = rolling(days)
    today = days[-1]
    # ---- twin
    if tw["missed_pc_on"]:
        item("info", "missed", f"{tw['missed_pc_on']} backtest trade(s) missed with the PC on ({usd(tw['missed_usd'])} in the backtest)")
    miss_days = sum(1 for b in days[-5:] if any(r.get("status") == "missed" and r.get("pc_on")
                                              for r in ((b.get("twin") or {}).get("nightly") or {}).get("rows") or []))
    if miss_days >= 2:
        item("act", "missed_repeat", f"backtest trades missed with the PC on, on {miss_days} of the last 5 sessions",
             "Open the PC dashboard > Execution: the reason is on each row (feed, late, sizer, refused).")
    es = tw["recent_entry_slip_med"]
    if es is not None and tw["recent_n"] >= 5 and es > SLIP_ACT:
        item("act", "slip", f"entries fill {es:+.1f} ticks worse than the backtest (median of the last {tw['recent_n']})",
             "Nothing to change on the PC; Claude checks the cost model (research queue).")
    if es is not None and tw["recent_n"] >= 8 and es > SLIP_PROPOSE:
        propose("cost-reserve", "zlarior", f"re-run the LIT gates with a {max(1, round(es))}-tick entry cost (live median {es:+.1f})",
                {"entry_slip_med_ticks": es, "n": tw["recent_n"]})
    reasons = tw["recent_miss_reasons"]
    if len(reasons) >= 3:
        top = max(set(reasons), key=reasons.count)
        propose("missed-entries", "zlarior", f"execution: {reasons.count(top)} missed entries in 10 sessions, mostly '{top}'",
                {"reasons": reasons[:6]})
    # ---- refused orders
    rj = rejects(today)
    rj_days = sum(1 for b in days[-5:] if rejects(b))
    if len(rj) >= REJECT_ACT or rj_days >= 2:
        item("act", "rejects", f"orders refused {len(rj)} time(s) today, on {rj_days} of the last 5 sessions"
             + (f": {rj[0]['error']}" if rj else ""), "Check NinjaTrader: account connected, right account Name, no 'Limit 0'.")
    elif rj:
        item("info", "reject", f"1 order refused: {rj[0]['error']}")
    # ---- no trades for N sessions (Zlarior + ATLAS entries)
    run_n = 0
    for b in reversed(days):
        if any(r.get("bot") in BOTS for r in entries(b)):
            break
        run_n += 1
    if run_n >= NO_TRADE_INFO:
        sess = days[-run_n:]
        bt = sum(1 for b in sess for r in ((b.get("twin") or {}).get("nightly") or {}).get("rows") or [] if r.get("status") != "extra")
        if run_n >= NO_TRADE_ACT and bt:
            item("act", "no_trades", f"no entry for {run_n} sessions while the backtest had {bt} trade(s)",
                 "Is the bot started and armed on the PC? START BOT, then check the Board.")
        else:
            item("info", "no_trades", f"no entry for {run_n} sessions" + (" (the backtest had none either: no setups)" if not bt else ""))
    # ---- bars
    if not bars_ok(today) and dt.date.fromisoformat(day).weekday() < 5:
        item("act", "bars", f"no NinjaTrader bars for {_md(day)}", "Keep NinjaTrader open with the LE_BarFeed chart (or the LE_Feed add-on).")
    # ---- edge light
    light = edge.get("light")
    if light == "RED" and (prev or {}).get("light") not in ("RED", None):
        item("act", "edge_red", f"edge light turned RED ({edge.get('line') or ''})".strip(),
             "A warning, not a switch: the bots keep trading. Hold off buying new evals until it is GREEN again.")
    elif light == "RED":
        item("info", "edge_red", "edge light RED (warning only)")
    # ---- rolling stats -> research proposals
    for bot in BOTS:
        S = roll[bot]
        if S.get("n", 0) >= 15 and S.get("pf") is not None and S["pf"] < 1.0:
            propose(f"{bot}-pf", bot, f"{NAMES[bot]} last {S['n']} trades PF {S['pf']} (< 1): re-check the edge on fresh bars "
                    "(tools/edge_health.py) before any change", {k: S.get(k) for k in ("n", "pf", "win_pct", "net_usd", "from", "to")})
    # ---- the data pipe itself
    if pipe and int(pipe.get("fails") or 0) >= 2:
        item("act", "pipe", "the PC could not send its data to the backup repo twice in a row",
             "On the PC, in the bot folder: python -X utf8 -m engine.datapipe run --signin (sign in as the backup account).")
    # ---- the text
    z, a = roll["zlarior"], roll["atlas"]

    def bot_line(nm, S):
        if not S.get("today_n"):
            return f"{nm} no trade"
        return f"{nm} {S['today_n']} trade{'s' if S['today_n'] != 1 else ''} {usd(S['today_usd'])}"
    twin_txt = ("live = backtest" if tw["verdict"] == "same" else "live differs from backtest" if tw["verdict"] == "differs"
                else "PC off" if tw["verdict"] == "pc off" else "no setups" if tw["verdict"] == "no trades" else "twin n/a")
    acts = [i for i in items if i["level"] == "act"]
    roll_txt = "; ".join(f"{NAMES[b]} last {roll[b]['n']}: PF {roll[b].get('pf')}, {usd(roll[b].get('net_usd'))}"
                         for b in BOTS if roll[b].get("n", 0) >= 5)
    text = (f"ZEUS {_md(day)}: {bot_line('Zlarior', z)}, {bot_line('ATLAS', a)} · {twin_txt}"
            + (f" (slip {usd(tw['slip_usd'])})" if tw["matched"] else "")
            + (f" · edge {light}" if light else "")
            + (f" · {roll_txt}" if roll_txt else "")
            + (" · needs you: " + "; ".join(i["text"] for i in acts[:2]) if acts else " · nothing needs you"))
    return {"v": VERSION, "day": day, "t": now, "text": text[:600], "action": bool(acts), "items": items, "light": light,
            "edge": edge, "twin": tw, "stats": roll, "sessions": len(days), "proposals": proposals}


# ================================================================================================ PC side
def push_text(R: dict) -> str:
    acts = [i for i in R["items"] if i["level"] == "act"]
    return "; ".join(f"{i['text']}. {i.get('fix', '')}".strip() for i in acts[:3])[:600]


def nightly(day: str, days_dir: str, out_dir: str = OUT, now=None, notify=None, emit=None,
            push_state: dict | None = None, edge: dict | None = None) -> dict:
    """Review `day` from the local day folders; write logs/zeus/, one board event, one push when it needs the owner."""
    from . import datapipe
    now = int(now if now is not None else time.time())
    days = datapipe.load_days(days_dir, upto=day)
    prev = None
    for b in reversed(days[:-1]):
        if b.get("review"):
            prev = b["review"]
            break
    R = review(days, edge if edge is not None else edge_light(), prev, push_state, now)
    os.makedirs(out_dir, exist_ok=True)
    datapipe._write_json(os.path.join(out_dir, f"review_{day}.json"), R)
    datapipe._write_json(os.path.join(out_dir, "latest.json"), R)
    sp = os.path.join(out_dir, "sent.json")
    sent = datapipe._read_json(sp, {}) or {}
    qp = os.path.join(out_dir, "research_queue.jsonl")
    have = {r.get("id") for r in datapipe._jl_read(qp)}
    new = [p for p in R["proposals"] if p["id"] not in have]
    if new:
        with open(qp, "a", encoding="utf-8") as fh:
            for p in new:
                fh.write(json.dumps(p, default=str) + "\n")
    out = {"review": R, "board": None, "pushed": None}
    if sent.get("board") != day:
        try:
            if emit is None:
                from .board_events import emit as _emit
                emit = _emit
            out["board"] = emit("daily_review", "", R["text"], {"day": day, "light": R.get("light"), "action": R["action"],
                                                                 "matched": R["twin"]["matched"], "missed": R["twin"]["missed"],
                                                                 "slip_usd": R["twin"]["slip_usd"], "acts": sum(1 for i in R["items"] if i["level"] == "act")})
            sent["board"] = day
        except Exception:
            pass
    if R["action"] and sent.get("push") != day:
        try:
            if notify is None:
                from .learn_loop import push_phone
                notify = lambda text, title: push_phone(text, title=title)   # noqa: E731
            out["pushed"] = notify(push_text(R), "ZEUS daily review")
            sent["push"] = day
        except Exception:
            pass
    datapipe._write_json(sp, sent)
    return out


def main(argv=None) -> int:
    import argparse
    from . import datapipe
    ap = argparse.ArgumentParser(prog="python -m engine.zeus_review", description="The ZEUS daily review (read-only)")
    ap.add_argument("--days-dir", default=datapipe.DAYS_DIR)
    ap.add_argument("--day", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    days = datapipe.load_days(a.days_dir, upto=a.day)
    R = review(days, edge_light())
    print(json.dumps(R, indent=1, default=str) if a.json else R["text"])
    for i in R["items"]:
        print(f"  [{'!!' if i['level'] == 'act' else '..'}] {i['text']}" + (f" -> {i['fix']}" if i.get("fix") else ""))
    for p in R["proposals"]:
        print(f"  [research] {p['what']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
